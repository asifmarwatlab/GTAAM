import threading
from pathlib import Path

import pytest

from terrain_client import TerrainApi
from terrain_client.errors import TerrainClientError
from terrain_client.launcher import BackendProcess

ROOT = Path(__file__).resolve().parents[2]


def test_backend_process_starts_serves_and_stops():
    backend = BackendProcess(ROOT)
    url = backend.start()
    try:
        assert backend.is_running()
        api = TerrainApi(url)
        assert api.health()["status"] == "ok" and len(api.health()["modules"]) == 6
        assert backend.start() == url                      # second start is a no-op
    finally:
        backend.stop()
    assert not backend.is_running()
    assert TerrainApi(url, timeout=1).is_alive() is False


def test_backend_process_rejects_a_wrong_folder(tmp_path):
    with pytest.raises(TerrainClientError, match="Not a backend folder"):
        BackendProcess(tmp_path).start()


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication([])


def _wait(qt_app, done, timeout_ms=5000):
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(lambda: loop.quit() if done() else None)
    poll.start(10)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    poll.stop()


def test_run_async_delivers_results_in_the_gui_thread(qt_app):
    from terrain_client.qt import run_async
    seen = {}

    def work(x, *, y):
        seen["worker_thread"] = threading.current_thread()
        return x + y

    run_async(work, 40, y=2,
              on_success=lambda r: seen.update(result=r, cb_thread=threading.current_thread()),
              on_finished=lambda: seen.update(finished=True))
    _wait(qt_app, lambda: seen.get("finished"))
    assert seen["result"] == 42
    assert seen["worker_thread"] is not threading.main_thread()        # the work ran off the GUI thread
    assert seen["cb_thread"] is threading.main_thread()                # the callback ran on it


def test_run_async_reports_api_errors(qt_app, client):
    from terrain_client.errors import ApiError
    from terrain_client.qt import run_async
    seen = {}
    api = TerrainApi(client=client)
    run_async(api.analysis.slope, "nope", on_success=lambda r: seen.update(ok=r),
              on_error=lambda e: seen.update(err=e), on_finished=lambda: seen.update(finished=True))
    _wait(qt_app, lambda: seen.get("finished"))
    assert "ok" not in seen and isinstance(seen["err"], ApiError) and seen["err"].code == "layer_not_found"


def test_qt_example_window_runs_end_to_end(tmp_path):
    """Real window (headless): start backend, open a DEM, run slope, draw both as pixmaps."""
    pytest.importorskip("PyQt6")
    import os
    import subprocess
    import sys

    from core.raster.writer import write_geotiff
    from tests.conftest import make_hill

    dem = write_geotiff(make_hill(), tmp_path / "dem.tif")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    done = subprocess.run([sys.executable, str(ROOT / "terrain_client/examples/qt_example.py"),
                           "--backend-dir", str(ROOT), "--selftest", dem],
                          env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
