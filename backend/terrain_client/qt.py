"""Run API calls off the GUI thread so the window never freezes.

    from terrain_client.qt import run_async

    def on_slope_done(result):            # runs in the GUI thread
        self.layers_panel.refresh()

    run_async(api.analysis.slope, layer_id,
              on_success=on_slope_done, on_error=self.show_error)

Callbacks always run in the thread that called run_async (normally the GUI thread), so they
may touch widgets safely. Needs PyQt6.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

log = logging.getLogger("terrain_client.qt")
_active: set["_Task"] = set()          # keeps running tasks alive until they report back


class _Signals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)
    finished = pyqtSignal()


class _Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], args: tuple, kwargs: dict):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()                     # created in the calling (GUI) thread

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:                  # noqa: BLE001 - hand every failure to the UI
            self.signals.failed.emit(exc)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


def run_async(fn: Callable[..., Any], *args: Any,
              on_success: Callable[[Any], None] | None = None,
              on_error: Callable[[BaseException], None] | None = None,
              on_finished: Callable[[], None] | None = None,
              pool: QThreadPool | None = None, **kwargs: Any) -> _Task:
    """Call fn(*args, **kwargs) in a worker thread.

    on_success(result)   called with the return value
    on_error(exc)        called with the exception (ApiError, ApiConnectionError, ...)
    on_finished()        called last, after either of the above (hide a spinner here)
    """
    task = _Task(fn, args, kwargs)
    _active.add(task)

    def _error(exc: BaseException) -> None:
        if on_error:
            on_error(exc)
        else:
            log.error("Unhandled error in %s: %s", getattr(fn, "__name__", fn),
                      "".join(traceback.format_exception(exc)))

    def _done() -> None:
        try:
            if on_finished:
                on_finished()
        finally:
            _active.discard(task)

    if on_success:
        task.signals.succeeded.connect(on_success)
    task.signals.failed.connect(_error)
    task.signals.finished.connect(_done)
    (pool or QThreadPool.globalInstance()).start(task)
    return task
