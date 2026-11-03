from __future__ import annotations
import os
import sys
from pathlib import Path
os.environ.setdefault("QT_API", "pyqt6")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont, QGuiApplication, QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend_runner import launch_backend, stop_backend  # noqa: E402   # <-- NEW
from ui.gui import MainWindow  # noqa: E402


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("A-GTAAM")
    app.setOrganizationName("A-GTAAM")
    app.setWindowIcon(QIcon(str(ROOT / "ui" / "assets" / "gtaam_tool_icon.png")))
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    qss = ROOT / "ui" / "styles.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    launch_backend()                       # <-- NEW: backend peeche start, window nahi rukti
    app.aboutToQuit.connect(stop_backend)  # <-- NEW: app band ho to backend bhi band

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())