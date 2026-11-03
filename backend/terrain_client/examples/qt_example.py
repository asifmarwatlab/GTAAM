"""Minimal PyQt6 window using terrain_client. Shows the three patterns the real UI needs:

  1. start the backend          BackendProcess(...).start()
  2. call the API off the GUI   run_async(api.analysis.slope, layer_id, on_success=...)
  3. show a map image           QPixmap().loadFromData(png_bytes)

Run:   py qt_example.py --backend-dir C:\\path\\to\\terrain_backend
   or  py qt_example.py --url http://127.0.0.1:8000       (backend already running)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))     # lets this run from the repo

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QVBoxLayout, QWidget)

from terrain_client import TerrainApi
from terrain_client.launcher import BackendProcess
from terrain_client.qt import run_async


class MainWindow(QWidget):
    image_shown = pyqtSignal(str)                     # layer id of the image just drawn

    def __init__(self, api: TerrainApi):
        super().__init__()
        self.api = api
        self.current_id: str | None = None
        self.setWindowTitle("Terrain Studio - client example")
        self.resize(900, 600)

        self.layers = QListWidget()
        self.layers.setMaximumWidth(240)
        self.layers.currentRowChanged.connect(self._layer_picked)
        self.image = QLabel("Open a DEM")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("Ready")

        buttons = QHBoxLayout()
        for text, slot in (("Open DEM...", lambda: self.open_dem()),
                           ("Slope", lambda: self.run_tool("slope")),
                           ("Hillshade", lambda: self.run_tool("hillshade")),
                           ("Statistics", self.show_statistics)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch()

        body = QHBoxLayout()
        body.addWidget(self.layers)
        body.addWidget(self.image, 1)
        root = QVBoxLayout(self)
        root.addLayout(buttons)
        root.addLayout(body, 1)
        root.addWidget(self.status)

    # ---- actions: each one starts a background call and returns immediately ----
    def open_dem(self, path: str | None = None) -> None:
        path = path or QFileDialog.getOpenFileName(self, "Open DEM", "", "GeoTIFF (*.tif *.tiff)")[0]
        if path:
            self._busy("Loading...")
            run_async(self.api.file.add_raster, path, on_success=self._layer_added,
                      on_error=self._error, on_finished=self._idle)

    def run_tool(self, name: str) -> None:
        if not self.current_id:
            return self.status.setText("Open a DEM first.")
        self._busy(f"Running {name}...")
        run_async(getattr(self.api.analysis, name), self.current_id, on_success=self._tool_done,
                  on_error=self._error, on_finished=self._idle)

    def show_statistics(self) -> None:
        if self.current_id:
            run_async(self.api.analysis.layer_statistics, self.current_id,
                      on_success=lambda s: self.status.setText(
                          f"min {s['min']:.1f}  max {s['max']:.1f}  mean {s['mean']:.1f}  std {s['std_dev']:.1f}"),
                      on_error=self._error)

    # ---- callbacks (always run in the GUI thread, so touching widgets is safe) ----
    def _layer_added(self, layer: dict) -> None:
        self._refresh_layers(select=layer["id"])

    def _tool_done(self, result: dict) -> None:
        self._refresh_layers(select=result["layer"]["id"])

    def _refresh_layers(self, select: str | None = None) -> None:
        run_async(self.api.file.layers, on_error=self._error,
                  on_success=lambda layers: self._fill_layers(layers, select))

    def _fill_layers(self, layers: list[dict], select: str | None) -> None:
        self.layers.blockSignals(True)
        self.layers.clear()
        for l in layers:
            self.layers.addItem(l["name"])
            self.layers.item(self.layers.count() - 1).setData(Qt.ItemDataRole.UserRole, l["id"])
        self.layers.blockSignals(False)
        for row, l in enumerate(layers):
            if l["id"] == select:
                self.layers.setCurrentRow(row)

    def _layer_picked(self, row: int) -> None:
        item = self.layers.item(row)
        if item is None:
            return
        self.current_id = item.data(Qt.ItemDataRole.UserRole)
        layer_id = self.current_id
        run_async(self.api.file.map_image, layer_id, "terrain", on_error=self._error,
                  on_success=lambda png: self._show_png(layer_id, png))

    def _show_png(self, layer_id: str, png: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(png)
        self.image.setPixmap(pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio))
        self.status.setText(f"Showing layer {layer_id}")
        self.image_shown.emit(layer_id)

    def _error(self, exc: BaseException) -> None:
        self.status.setText(f"Error: {exc}")             # ApiError.message is already user-friendly

    def _busy(self, text: str) -> None:
        self.status.setText(text)
        self.setCursor(Qt.CursorShape.BusyCursor)

    def _idle(self) -> None:
        self.unsetCursor()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-dir", help="start the backend from this folder")
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="use a backend that is already running")
    ap.add_argument("--selftest", metavar="DEM", help="headless check: load DEM, run slope, exit 0/1")
    args = ap.parse_args()

    backend = BackendProcess(args.backend_dir) if args.backend_dir else None
    app = QApplication(sys.argv)
    api = TerrainApi(backend.start() if backend else args.url)
    win = MainWindow(api)
    app.aboutToQuit.connect(lambda: backend and backend.stop())
    win.show()

    if args.selftest:
        shown: list[str] = []
        def on_image(layer_id: str) -> None:
            shown.append(layer_id)
            if len(shown) == 1:
                win.run_tool("slope")                       # DEM drawn -> now run a tool
            elif len(shown) == 2 and win.image.pixmap() is not None and not win.image.pixmap().isNull():
                app.exit(0)
        win.image_shown.connect(on_image)
        QTimer.singleShot(25_000, lambda: app.exit(1))     # give up
        QTimer.singleShot(0, lambda: win.open_dem(args.selftest))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
