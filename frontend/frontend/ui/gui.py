from __future__ import annotations
from datetime import datetime
import ctypes
import json
import sys
import threading
from pathlib import Path
import traceback
from backend_runner import API_PREFIX, BASE_URL, wait_until_ready
from PyQt6.QtCore import (
    QEvent, QObject, QPoint, QPointF, QRectF, QRunnable, QSize, Qt, QThreadPool, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFont, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QPolygonF, QShortcut,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QInputDialog, QMenu, QScrollArea, QSplitter, QToolButton, QVBoxLayout, QWidget, QApplication,
)
import httpx
import numpy as np

from click import group
from matplotlib.pyplot import box
from ui.panels.layer_statistics import MapBox, _project_defaults
from ui.panels.attribute_table import AttributeTableWindow
import Analysis
import file as file_tab
import Terrain_Editing
import Terrain_Mosaic
import Tools
import View
from ui.panels.icon_generator import icon, pixmap
from ui.panels.layer_statistics import (
    ContentsPane, InspectorPane, Layer, SampleWorkspace, SettingsForm, set_settings_provider, invalidate_project_defaults,
)
from ui.panels import map_geometry
from ui.panels.map_bar import PROFILE_COLORS, MapSection
from ui.panels.project_settings import ProjectSettingsDialog

# order of the ribbon tabs
TAB_MODULES = [file_tab, View, Analysis, Tools, Terrain_Editing, Terrain_Mosaic]
DEFAULT_TAB = "File"
NOTE_TEXT = "AI-enabled Geospatial Terrain Analytics & Adaptive Modification"
PROJECT_TITLE = "Untitled"
APP_NAME ="GTAAM"

# ----------------------------------------------------------------------------
# backend connection helpers (project files, quality tools)
# ----------------------------------------------------------------------------
PROJECT_EXT = ".gtm"
PROJECT_FILTER = "A-GTAAM project (*.gtm);;Older projects (*.agtaam *.json);;All files (*)"
VECTOR_FILTER = ("Vector files (*.shp *.geojson *.json *.gpkg *.kml *.kmz *.gpx *.gml *.fgb *.csv *.zip "
                 "*.dxf *.tab *.mif);;All files (*)")
VECTOR_COLORS = ["#1f6f9a", "#c0392b", "#2e8b57", "#8e44ad", "#d68910", "#16a085"]


def _message(exc: Exception) -> str:
    """'API error 400: {"error":..,"message":..}' -> just the message."""
    text = str(exc)
    if "{" in text:
        try:
            body = json.loads(text[text.index("{"):])
            return str(body.get("message") or body.get("detail") or body.get("error") or text)
        except (ValueError, AttributeError):
            pass
    return text


def _quality_source(win, values: dict):
    """The raster picked in the tool panel's layer drop-down (matched by display name)."""
    src = next((l for l in win.ws.rasters() if l.name == values.get("raster_layer")), None)
    if src is None:
        raise ValueError("Load a raster DEM before running this analysis.")
    return src


_QUALITY_EXTRA = """
    QLabel#qTitle { color: #1b2530; font-size: 15px; font-weight: 700; }
    QLabel#qSub { color: #6b737b; font-size: 11px; }
    QLabel#qBig { color: #1b2530; font-size: 24px; font-weight: 700; }
    QLabel#qPillOk { background: #e3f4ea; color: #1d7a45; border-radius: 9px; padding: 3px 10px; font-size: 11px; font-weight: 700; }
    QLabel#qPillWarn { background: #fdf0d9; color: #9a6410; border-radius: 9px; padding: 3px 10px; font-size: 11px; font-weight: 700; }
    QLabel#qStatName { color: #6b737b; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
    QLabel#qStatValue { color: #1b2530; font-size: 14px; font-weight: 700; }
    QPushButton#qClose { background: #1f6f9a; color: white; border: none; border-radius: 8px; padding: 7px 22px; font-weight: 600; }
    QPushButton#qClose:hover { background: #185a7f; }
"""


def _quality_header(layout, title: str, layer: str, pill: tuple[str, str] | None = None) -> None:
    """Title, layer subtitle and an optional status pill at the top of a Quality & Statistics window."""
    row = QHBoxLayout()
    col = QVBoxLayout()
    col.setSpacing(1)
    t = QLabel(title)
    t.setObjectName("qTitle")
    sub = QLabel(layer)
    sub.setObjectName("qSub")
    col.addWidget(t)
    col.addWidget(sub)
    row.addLayout(col, 1)
    if pill:
        p = QLabel(pill[0])
        p.setObjectName("qPillOk" if pill[1] == "ok" else "qPillWarn")
        row.addWidget(p, 0, Qt.AlignmentFlag.AlignTop)
    layout.addLayout(row)


def _quality_stat_grid(rows: list[tuple[str, str]], columns: int = 2) -> QGridLayout:
    grid = QGridLayout()
    grid.setHorizontalSpacing(28)
    grid.setVerticalSpacing(12)
    for i, (name, value) in enumerate(rows):
        cell = QVBoxLayout()
        cell.setSpacing(1)
        n = QLabel(name.upper())
        n.setObjectName("qStatName")
        v = QLabel(value)
        v.setObjectName("qStatValue")
        cell.addWidget(n)
        cell.addWidget(v)
        grid.addLayout(cell, i // columns, i % columns)
    return grid


class _QualityDialogBase(QDialog):
    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        self.setObjectName("measureWindow")
        self.setWindowTitle(title)
        self.setStyleSheet(MeasureWindow.style() + _QUALITY_EXTRA)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        card = QFrame()
        card.setObjectName("measureCard")
        outer.addWidget(card)
        self.body = QVBoxLayout(card)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(12)
        self._footer = outer

    def add_close(self) -> None:
        btn = QPushButton("Close")
        btn.setObjectName("qClose")
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        self._footer.addLayout(row)


class HistogramDialog(_QualityDialogBase):
    """Bar chart of a layer's value distribution (counts per bin)."""

    def __init__(self, parent, name: str, res: dict, log: bool) -> None:
        super().__init__(parent, f"Histogram \u00b7 {name}")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from matplotlib.ticker import FuncFormatter

        self.resize(760, 560)
        edges = np.asarray(res["bin_edges"], dtype=float)
        counts = np.asarray(res["counts"], dtype=float)
        _quality_header(self.body, "Histogram", name)
        self.body.addLayout(_quality_stat_grid([
            ("Pixels counted", f"{int(res['pixels']):,}"),
            ("Bins", f"{int(res['bins'])}"),
            ("Lowest value", f"{edges[0]:,.2f}"),
            ("Highest value", f"{edges[-1]:,.2f}"),
        ], columns=4))
        rule = QFrame()
        rule.setObjectName("measureRule")
        self.body.addWidget(rule)

        fig = Figure(figsize=(7, 4.2), tight_layout=True, facecolor="white")
        ax = fig.add_subplot(111)
        ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge",
               color="#1f6f9a", edgecolor="white", linewidth=0.5)
        if log:
            ax.set_yscale("log")
        ax.set_xlabel("Pixel value", color="#5b6670", fontsize=9)
        ax.set_ylabel("Number of pixels" + (" (log scale)" if log else ""), color="#5b6670", fontsize=9)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(colors="#5b6670", labelsize=8)
        ax.grid(axis="y", color="#e6eaee", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#cfd6dc")
        self.body.addWidget(FigureCanvasQTAgg(fig), 1)
        self.add_close()


class NoDataDialog(_QualityDialogBase):
    def __init__(self, parent, name: str, r: dict, width, height) -> None:
        super().__init__(parent, f"NoData Check \u00b7 {name}")
        self.resize(460, 330)
        clean = r["status"] == "clean"
        _quality_header(self.body, "NoData Check", name,
                        ("No NoData found", "ok") if clean else ("Contains NoData", "warn"))
        big = QLabel(f"{r['percent']}%")
        big.setObjectName("qBig")
        self.body.addWidget(big)
        note = QLabel("of the cells are empty (NoData)" if not clean else "of the cells are empty \u2014 the raster is complete")
        note.setObjectName("qSub")
        self.body.addWidget(note)
        rule = QFrame()
        rule.setObjectName("measureRule")
        self.body.addWidget(rule)
        rows = [("NoData cells", f"{r['nodata_count']:,} of {r['total']:,}"),
                ("Raster size", f"{width:,} \u00d7 {height:,}" if width and height else "\u2014"),
                ("Rows touched", f"{r['rows_affected']:,}" + (f" of {height:,}" if height else "")),
                ("Columns touched", f"{r['columns_affected']:,}" + (f" of {width:,}" if width else ""))]
        self.body.addLayout(_quality_stat_grid(rows))
        self.add_close()


class OutlierDialog(_QualityDialogBase):
    def __init__(self, parent, name: str, r: dict, method: str) -> None:
        super().__init__(parent, f"Outlier Check \u00b7 {name}")
        self.resize(480, 360)
        none = r["outlier_count"] == 0
        _quality_header(self.body, "Outlier Check", name,
                        ("No outliers", "ok") if none else ("Outliers found", "warn"))
        big = QLabel(f"{r['outlier_count']:,}")
        big.setObjectName("qBig")
        self.body.addWidget(big)
        note = QLabel(f"cells outside the normal range ({r['percent']}% of valid cells)")
        note.setObjectName("qSub")
        self.body.addWidget(note)
        rule = QFrame()
        rule.setObjectName("measureRule")
        self.body.addWidget(rule)
        lo = f"{r['lowest_outlier']:,.2f}" if r["lowest_outlier"] is not None else "\u2014"
        hi = f"{r['highest_outlier']:,.2f}" if r["highest_outlier"] is not None else "\u2014"
        rows = [("Method", f"{'IQR' if method == 'iqr' else 'Z-score'} (threshold {r['threshold']})"),
                ("Normal range", f"{r['lower_bound']:,.2f} to {r['upper_bound']:,.2f}"),
                ("Lowest outlier", lo), ("Highest outlier", hi)]
        self.body.addLayout(_quality_stat_grid(rows))
        self.add_close()


class _PixelSampleSignals(QObject):
    finished = pyqtSignal(object, object)


class _PixelSampleWorker(QRunnable):
    _http = httpx.Client(
        timeout=3.0,
        limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
    )

    def __init__(self, layer_id: str, row: int, col: int) -> None:
        super().__init__()
        self.layer_id = layer_id
        self.row = row
        self.col = col
        self.signals = _PixelSampleSignals()

    def run(self) -> None:
        try:
            with self._http.stream(
                "GET",
                f"{BASE_URL}{API_PREFIX}/file/add-data/layers/{self.layer_id}/pixel",
                params={"row": self.row, "col": self.col},
            ) as response:
                response.read()
                response.raise_for_status()
                result = response.json()
            self.signals.finished.emit(self, result)
        except Exception as exc:
            self.signals.finished.emit(self, exc)


def _wrap_label(text: str) -> str:
    """Two-line label for long ribbon captions."""
    if len(text) <= 12 or " " not in text:
        return text
    words = text.split(" ")
    best = min(range(1, len(words)),
               key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


# ----------------------------------------------------------------------------
# ribbon
# ----------------------------------------------------------------------------
class RibbonBar(QFrame):
    toolTriggered = pyqtSignal(dict)

    def __init__(self, is_on, is_available) -> None:
        super().__init__()
        self.setObjectName("ribbon")
        self.setFixedHeight(118)
        self._is_on = is_on
        self._is_available = is_available
        self._toggles: dict[str, QToolButton] = {}
        self._inner: QWidget | None = None
        self._outer = QVBoxLayout(self)
        self.backend_ids: dict[str,str]={}
        self._outer.setContentsMargins(0, 0, 0, 0)

    def show_tab(self, module) -> None:
        if self._inner is not None:
            self._inner.setParent(None)
            self._inner.deleteLater()
        self._toggles.clear()
        inner = QWidget()
        row = QHBoxLayout(inner)
        row.setContentsMargins(12, 6, 14, 6)
        row.setSpacing(0)
        for i, group in enumerate(module.GROUPS):
            if i:
                sep = QFrame()
                sep.setObjectName("ribbonSeparator")
                sep.setFixedWidth(1)
                row.addSpacing(8)
                row.addWidget(sep)
                row.addSpacing(8)
            row.addWidget(self._build_group(group))
        row.addStretch(1)


        self._outer.addWidget(inner)
        self._inner = inner
        self.refresh_checks()

    def _build_group(self, group: dict) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(2)
        stack: QVBoxLayout | None = None
        for tool in group["tools"]:
            tool = dict(tool, group_label=group["label"])
            if tool.get("size") == "small":
                if stack is None or stack.count() >= 3:
                    stack = QVBoxLayout()
                    stack.setSpacing(2)
                    stack.setContentsMargins(0, 0, 0, 0)
                    tools_row.addLayout(stack)
                    tools_row.setAlignment(stack, Qt.AlignmentFlag.AlignVCenter)
                stack.addWidget(self._small_button(tool))
            else:
                stack = None
                tools_row.addWidget(self._large_button(tool))
        tools_row.addStretch(0)
        v.addLayout(tools_row, 1)
        label = QLabel(group["label"])
        label.setObjectName("ribbonLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(label)
        return box

    def _wire(self, btn: QToolButton, tool: dict) -> None:
        btn.setToolTip(tool.get("tip") or tool["label"])
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, t=tool: self.toolTriggered.emit(t))
        if tool.get("kind") == "toggle":
            btn.setCheckable(True)
            self._toggles[tool["toggle"]] = btn

    def _large_button(self, tool: dict) -> QToolButton:
        b = QToolButton()
        b.setObjectName("ribbonButton")
        b.setText(_wrap_label(tool["label"]))
        b.setIcon(icon(tool["icon"], "#244557", 26))
        b.setIconSize(QSize(26,26))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setMinimumWidth(78)
        b.setFixedHeight(75)
        self._wire(b, tool)
        return b

    def _small_button(self, tool: dict) -> QToolButton:
        b = QToolButton()
        b.setObjectName("ribbonSmall")
        b.setText(tool["label"])
        b.setIcon(icon(tool["icon"], "#244557", 18))
        b.setIconSize(QSize(18, 18))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setMinimumWidth(138)
        b.setFixedHeight(23)
        self._wire(b, tool)
        return b

    def refresh_checks(self) -> None:
        for key, btn in self._toggles.items():
            btn.setEnabled(self._is_available(key))
            btn.blockSignals(True)
            btn.setChecked(bool(self._is_on(key)))
            btn.blockSignals(False)


# ----------------------------------------------------------------------------
# modal tool dialog (used for kind = "dialog")
# ----------------------------------------------------------------------------
class BackendStatus(QLabel):
    """Small pill in the status bar: is the backend (the "kitchen") reachable?"""
    _result = pyqtSignal(bool)
    _STYLE = {
        "connecting": ("#b7791f", "#fdf6e3", "#f1dfb0", "Connecting to backend…"),
        "online": ("#1e7e4a", "#e8f6ee", "#bfe3cf", "Backend connected"),
        "offline": ("#c0392b", "#fdecea", "#f3c3bd", "Backend offline"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state, self._busy = "", False
        self.setObjectName("backendStatus")
        self._apply("connecting")
        self._result.connect(self._on_result)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(2000)
        self._poll()

    def _poll(self) -> None:
        if self._busy:
            return
        self._busy = True

        def ping() -> None:                      # background thread: the window never freezes
            try:
                ok = httpx.get(BASE_URL + "/health", timeout=1.5).status_code == 200
            except Exception:
                ok = False
            self._result.emit(ok)

        threading.Thread(target=ping, daemon=True).start()

    def _on_result(self, ok: bool) -> None:
        self._busy = False
        if ok:
            self._apply("online")
        elif self._state == "online":
            self._apply("offline")

    def _apply(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        fg, bg, border, text = self._STYLE[state]
        self.setText(f"●  {text}")
        self.setToolTip(f"Backend: {BASE_URL}")
        self.setStyleSheet(f"QLabel#backendStatus {{ color:{fg}; background:{bg}; border:1px solid {border};"
                           f" border-radius:10px; padding:2px 10px; font-size:12px; font-weight:600; }}")


def _friendly_error(exc: Exception) -> str:
    """One readable sentence for the status line under a Run button."""
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 160 else text[:157] + "\u2026"


class VectorLayerChooser(QDialog):
    """A GeoPackage, geodatabase or DXF can hold many layers: tick the ones to add."""

    def __init__(self, parent, file_name: str, names: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add vector layers")
        self.setModal(True)
        self.setObjectName("measureWindow")
        self.setStyleSheet(MeasureWindow.style() + _QUALITY_EXTRA)
        self.setMinimumWidth(380)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        card = QFrame()
        card.setObjectName("measureCard")
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        v.addWidget(_card_title("Choose layers"))
        sub = QLabel(f"{file_name} holds {len(names)} layers. Tick the ones to add to the map.")
        sub.setObjectName("qSub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { border: 1px solid #dde2e7; border-radius: 8px; padding: 4px; }"
                                "QListWidget::item { padding: 5px 6px; }")
        for n in names:
            it = QListWidgetItem(n)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if len(names) <= 5 else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        v.addWidget(self.list)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Add")
        ok.setObjectName("primaryButton")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)

    def chosen(self) -> list[str]:
        return [self.list.item(i).text() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]


class ToolDialog(QDialog):
    def __init__(self, parent, tool: dict, raster_names: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(tool["label"])
        self.setModal(True)
        self.setMinimumWidth(420)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(14)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(pixmap(tool.get("icon", "grid"), "#1f6f9a", 26))
        title = QLabel(tool["label"])
        title.setObjectName("dialogTitle")
        head.addWidget(ic)
        head.addWidget(title, 1)
        v.addLayout(head)
        self.form = SettingsForm(tool.get("fields", []), raster_names)
        v.addWidget(self.form)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(tool.get("run_label", "OK"))
        ok.setObjectName("primaryButton")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)


class ProjectNameDialog(QDialog):
    def __init__(self, project_name: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("projectNameDialog")
        self.setWindowTitle("Name the project")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.project_name = ""
        self.setStyleSheet("""
            QDialog#projectNameDialog {
                background: #e4e7ea;
            }
            QFrame#projectNameCard {
                background: #f4f5f6;
                border: 1px solid #d0d4d8;
                border-radius: 12px;
            }
            QLabel#projectNameEyebrow {
                color: #6b737b;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#projectNameHeading {
                color: #252a2f;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#projectNameDescription {
                color: #626a72;
                font-size: 12px;
            }
            QLineEdit#projectNameInput {
                background: #ffffff;
                color: #252a2f;
                border: 1px solid #c5cbd1;
                border-radius: 7px;
                padding: 9px 10px;
                selection-background-color: #68737d;
            }
            QLineEdit#projectNameInput:focus {
                border: 1px solid #68737d;
            }
            QLabel#projectNameError {
                color: #8b3f3f;
                font-size: 11px;
            }
            QPushButton#projectNameCancel {
                background: #e4e7ea;
                color: #343a40;
                border: 1px solid #cbd0d5;
                border-radius: 6px;
                padding: 7px 14px;
            }
            QPushButton#projectNameCancel:hover {
                background: #d9dde1;
            }
            QPushButton#projectNameSave {
                background: #495057;
                color: #f8f9fa;
                border: 1px solid #495057;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
            }
            QPushButton#projectNameSave:hover {
                background: #343a40;
                border-color: #343a40;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        card = QFrame()
        card.setObjectName("projectNameCard")
        body = QVBoxLayout(card)
        body.setContentsMargins(22, 20, 22, 18)
        body.setSpacing(10)

        eyebrow = QLabel("PROJECT SETTINGS")
        eyebrow.setObjectName("projectNameEyebrow")
        heading = QLabel("Name your project")
        heading.setObjectName("projectNameHeading")
        description = QLabel("Choose a name that will be saved with this project.")
        description.setObjectName("projectNameDescription")
        description.setWordWrap(True)
        self.name_input = QLineEdit(project_name)
        self.name_input.setObjectName("projectNameInput")
        self.name_input.setPlaceholderText("Enter project name")
        self.name_input.selectAll()
        self.error_label = QLabel("Enter a project name to continue.")
        self.error_label.setObjectName("projectNameError")
        self.error_label.hide()

        body.addWidget(eyebrow)
        body.addWidget(heading)
        body.addWidget(description)
        body.addSpacing(4)
        body.addWidget(self.name_input)
        body.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("projectNameCancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save name")
        save.setObjectName("projectNameSave")
        save.setDefault(True)
        save.clicked.connect(self._accept_name)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        body.addSpacing(4)
        body.addLayout(buttons)
        outer.addWidget(card)
        self.name_input.returnPressed.connect(self._accept_name)

    def _accept_name(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self.error_label.show()
            self.name_input.setFocus()
            return
        self.project_name = name
        self.accept()


def _card_title(text: str) -> QLabel:
    """Centred heading at the top of a measure window's card."""
    t = QLabel(text)
    t.setObjectName("measureTitle")
    t.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
    return t


class MeasureHistory(QWidget):
    """Under a Distance or Area result: the choice to keep earlier results on the map, and a small card for each one
    (with its own x to discard it)."""
    keepChanged = pyqtSignal(bool)
    removeRequested = pyqtSignal(int)        # the id of the line or area to discard
    clearRequested = pyqtSignal()

    def __init__(self, what: str) -> None:
        super().__init__()
        self.cards: dict[int, QFrame] = {}
        self.unit_key: dict[int, str] = {}   # id -> the units its numbers were measured in
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(5)
        row = QHBoxLayout()
        self.keep = QCheckBox(f"Keep earlier {what} on the map")
        self.keep.setObjectName("measureName")
        self.keep.setChecked(True)
        self.keep.toggled.connect(self.keepChanged.emit)
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.setObjectName("histClear")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(lambda _c=False: self.clearRequested.emit())
        row.addWidget(self.keep)
        row.addStretch(1)
        row.addWidget(self.clear_btn)
        lay.addLayout(row)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("histScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setMaximumHeight(200)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(5)
        self.list.addStretch(1)
        self.scroll.setWidget(inner)
        lay.addWidget(self.scroll)
        self._sync()

    def set_entry(self, sid: int, title: str, sub: str, color: str) -> None:
        card = self.cards.get(sid)
        if card is None:
            card = QFrame()
            card.setObjectName("histCard")
            h = QHBoxLayout(card)
            h.setContentsMargins(8, 6, 6, 6)
            h.setSpacing(8)
            num = QLabel(str(sid))
            num.setFixedSize(20, 20)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(f"background: {color}; color: #ffffff; border-radius: 10px; font-size: 11px; font-weight: 700;")
            col = QVBoxLayout()
            col.setSpacing(0)
            card._title = QLabel("")
            card._title.setObjectName("measureValue")
            card._sub = QLabel("")
            card._sub.setObjectName("measureCaption")
            col.addWidget(card._title)
            col.addWidget(card._sub)
            x = QToolButton()
            x.setObjectName("histX")
            x.setText("\u2715")
            x.setToolTip("Discard this one")
            x.setCursor(Qt.CursorShape.PointingHandCursor)
            x.clicked.connect(lambda _c=False, i=sid: self.removeRequested.emit(i))
            h.addWidget(num)
            h.addLayout(col, 1)
            h.addWidget(x)
            self.list.insertWidget(self.list.count() - 1, card)
            self.cards[sid] = card
        card._title.setText(title)
        card._sub.setText(sub)
        card._sub.setVisible(bool(sub))
        self._sync()

    def remove(self, sid: int) -> None:
        card = self.cards.pop(sid, None)
        self.unit_key.pop(sid, None)
        if card is not None:
            card.setParent(None)
            card.deleteLater()
        self._sync()

    def clear(self) -> None:
        for sid in list(self.cards):
            self.remove(sid)
        self.unit_key.clear()

    def _sync(self) -> None:
        has = bool(self.cards)
        self.scroll.setVisible(has)
        self.clear_btn.setVisible(has)


def _saved_unit(name: str, default: str) -> str:
    """The unit chosen in Project Settings (e.g. 'square_metres' -> 'square metres'), else the window's own default."""
    value = _project_defaults().get(name)
    return str(value).replace("_", " ") if value else default


class MeasureWindow(QDialog):
    """A small floating Measure box, like ArcMap's: it updates as points are clicked and has a
    units menu. Segment is the last straight piece, Length is the whole line."""
    unitsChanged = pyqtSignal(str)          # backend unit name: metres, kilometres, feet, miles
    closed = pyqtSignal()

    UNITS = [("Metres", "metres"), ("Kilometres", "kilometres"), ("Feet", "feet"), ("Miles", "miles")]
    DEFAULT_UNIT = "kilometres"

    STYLE = """
            QDialog#measureWindow { background: #eef1f4; }
            QFrame#measureCard { background: #ffffff; border: 1px solid #dde2e7; border-radius: 12px; }
            QLabel#measureMethod { color: #1b2530; font-size: 13px; font-weight: 700; }
            QLabel#measureLayer { color: #6b737b; font-size: 11px; }
            QLabel#measureHint { color: #2f6585; font-size: 12px; background: #eaf3f8; border-radius: 7px; padding: 7px 9px; }
            QLabel#measureSection { color: #6b737b; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#measureName { color: #5b6670; font-size: 12px; }
            QLabel#measureValue { color: #1b2530; font-size: 13px; font-weight: 700; }
            QLabel#measureBig { color: #1f6f9a; font-size: 15px; font-weight: 700; }
            QLabel#measureTitle { color: #1b2530; font-size: 15px; font-weight: 700; padding-bottom: 2px; }
            QLabel#measureHero { color: #1f6f9a; font-size: 24px; font-weight: 700; }
            QLabel#measureCaption { color: #8a949c; font-size: 11px; }
            QLabel#measureNote { color: #7a6a3a; font-size: 11px; }
            QFrame#measureRule { background: #edf0f3; max-height: 1px; min-height: 1px; border: none; }
            QFrame#histCard { background: #f6f8fa; border: 1px solid #e1e5e9; border-radius: 8px; }
            QToolButton#histX { border: none; color: #8a949c; font-size: 13px; padding: 2px 5px; }
            QToolButton#histX:hover { color: #c0392b; }
            QPushButton#histClear { border: none; color: #1f6f9a; font-size: 12px; padding: 2px 4px; background: transparent; }
            QPushButton#histClear:hover { text-decoration: underline; }
            QScrollArea#histScroll, QScrollArea#histScroll > QWidget > QWidget { background: transparent; border: none; }
            QCheckBox#measureName { color: #5b6670; font-size: 12px; spacing: 6px; }
            QComboBox { background: #f6f8fa; color: #1b2530; border: 1px solid #cfd6dc; border-radius: 8px;
                        padding: 5px 30px 5px 10px; min-height: 20px; font-size: 12px; }
            QComboBox:hover, QComboBox:on { background: #ffffff; border-color: #1f6f9a; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 26px;
                                   border: none; border-left: 1px solid #e1e5e9;
                                   border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
            QComboBox::down-arrow { image: url(__CHEVRON__); width: 12px; height: 8px; }
            QComboBox QAbstractItemView { background: #ffffff; color: #1b2530; border: 1px solid #cfd6dc;
                                          selection-background-color: #e6f1f7; selection-color: #1f6f9a; padding: 4px; outline: 0; }
    """

    @classmethod
    def style(cls) -> str:
        """The style sheet with the drop-down arrow filled in (a small arrow image is drawn once into the temp folder)."""
        import tempfile
        path = Path(tempfile.gettempdir()) / "gtaam_combo_arrow.png"
        try:
            pm = QPixmap(12, 8)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#495057"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolyline(QPolygonF([QPointF(1.5, 1.8), QPointF(6, 6.2), QPointF(10.5, 1.8)]))
            painter.end()
            pm.save(str(path), "PNG")
        except Exception:
            pass
        return cls.STYLE.replace("__CHEVRON__", path.as_posix())

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("measureWindow")
        self.setWindowTitle("Measure")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        self.setMinimumWidth(310)
        self.setStyleSheet(self.style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("measureCard")
        body = QVBoxLayout(card)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(5)

        body.addWidget(_card_title("Distance"))
        top = QHBoxLayout()
        units_label = QLabel("Units")
        units_label.setObjectName("measureName")
        self.units = QComboBox()
        for text, key in self.UNITS:
            self.units.addItem(text, key)
        self.units.setCurrentIndex(max(0, self.units.findData(_saved_unit("distance_unit", self.DEFAULT_UNIT))))
        self.units.currentIndexChanged.connect(lambda _i: self.unitsChanged.emit(self.units.currentData()))
        top.addWidget(units_label)
        top.addWidget(self.units, 1)
        body.addLayout(top)

        self.method = QLabel("Line measurement")
        self.method.setObjectName("measureMethod")
        self.layer = QLabel("")
        self.layer.setObjectName("measureLayer")
        self.hint = QLabel("Click the first point on the map.")
        self.hint.setObjectName("measureHint")
        self.hint.setWordWrap(True)
        body.addWidget(self.hint)

        self.rows: dict[str, tuple[QLabel, QLabel]] = {}
        self.result_box = QWidget()
        rl = QVBoxLayout(self.result_box)
        rl.setContentsMargins(0, 4, 0, 0)
        rl.setSpacing(3)
        for key, name, big in (("segment", "Segment", False), ("length", "Length", True)):
            rl.addLayout(self._row(key, name, big))
        self.elev_rule = QFrame()
        self.elev_rule.setObjectName("measureRule")
        rl.addWidget(self.elev_rule)
        for key, name in (("start", "Start elevation"), ("end", "End elevation"),
                          ("diff", "Elevation difference")):
            rl.addLayout(self._row(key, name, False))
        self.note = QLabel("Elevation is not available: a point is outside the DEM or on NoData.")
        self.note.setObjectName("measureNote")
        self.note.setWordWrap(True)
        rl.addWidget(self.note)
        body.addWidget(self.result_box)
        self.history = MeasureHistory("lines")
        body.addWidget(self.history)
        outer.addWidget(card)
        self.show_waiting()

    def _row(self, key: str, name: str, big: bool) -> QHBoxLayout:
        line = QHBoxLayout()
        a = QLabel(name + ":")
        a.setObjectName("measureName")
        b = QLabel("")
        b.setObjectName("measureBig" if big else "measureValue")
        b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line.addWidget(a)
        line.addStretch(1)
        line.addWidget(b)
        self.rows[key] = (a, b)
        return line

    def set_layer(self, name: str, geographic: bool) -> None:
        self.method.setText("Distance")
        self.layer.setText(name)

    def show_waiting(self, text: str = "Click the first point on the map.") -> None:
        self.hint.setText(text)
        self.hint.setVisible(type(self).__name__ not in _HINTS_SEEN)
        self.result_box.hide()
        self.adjustSize()

    def show_result(self, res: dict, finished: bool, want_elevation: bool) -> None:
        unit = res["unit"]
        d = 3 if unit in ("km", "mi") else 2
        self.hint.setText("Double-click to finish \u00b7 Right-click removes the last point" if not finished
                          else "Line finished. Click the map to measure a new line.")
        self.hint.setVisible(type(self).__name__ not in _HINTS_SEEN)
        if finished:
            _HINTS_SEEN.add(type(self).__name__)       # the tips are shown once, then stay out of the way
        self.rows["segment"][1].setText(f"{res['segments'][-1]:,.{d}f} {unit}")
        self.rows["length"][1].setText(f"{res['total']:,.{d}f} {unit}")
        el = res.get("elevation")
        eu = res.get("elevation_unit", unit)
        ed = 3 if eu in ("km", "mi") else 2
        for key in ("start", "end", "diff"):
            for w in self.rows[key]:
                w.setVisible(bool(el))
        self.elev_rule.setVisible(bool(el))
        self.note.setVisible(not el and want_elevation)
        if el:
            self.rows["start"][1].setText(f"{el['start']:,.{ed}f} {eu}")
            self.rows["end"][1].setText(f"{el['end']:,.{ed}f} {eu}")
            self.rows["diff"][1].setText(f"{el['difference']:+,.{ed}f} {eu}")
        self.result_box.show()
        self.adjustSize()

    def closeEvent(self, e) -> None:
        self.closed.emit()
        super().closeEvent(e)

    def reject(self) -> None:           # Esc or the close button
        self.close()


class ProfileChart(QWidget):
    """Draws distance (across) against height (up) for the profile lines, one colour per line (the same colour as
    the line on the map). Move the mouse over it to read the values of every line at that distance."""

    profileClicked = pyqtSignal(int)          # a name in the legend was clicked: the profile's number (0, 1, 2 ...)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(470, 250)
        self.setMouseTracking(True)
        self.selected: int | None = None      # the profile whose numbers are shown under the graph
        self._legend_rects: list[tuple[QRectF, int]] = []
        self.series: list[dict] = []          # {"res": profile result, "color": "#hex", "name": "Profile 1", "idx": 0}
        self.res: dict | None = None          # the newest profile (used for the true-scale box)
        self.true_scale = False
        self._hover: float | None = None      # distance along the axis under the mouse

    def set_series(self, series: list[dict], true_scale: bool, selected: int | None = None) -> None:
        self.selected = selected
        self.series = [s for s in series if s.get("res")]
        self.res = self.series[-1]["res"] if self.series else None
        self.true_scale, self._hover = true_scale, None
        self.update()

    def set_result(self, res: dict | None, true_scale: bool) -> None:
        self.set_series([{"res": res, "color": "#1f6f9a", "name": ""}] if res else [], true_scale)

    def _has_data(self) -> bool:
        return any(v is not None for s in self.series for v in s["res"]["elevation"])

    def _data_range(self):
        """Lowest and highest height on all the lines, with a little room above and below."""
        el = [v for s in self.series for v in s["res"]["elevation"] if v is not None]
        lo, hi = min(el), max(el)
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.08
        return lo - pad, hi + pad

    def _total(self) -> float:
        """The distance axis runs to the longest line."""
        return max((s["res"]["distance"][-1] or 0.0) for s in self.series) or 1.0

    # plot rectangle inside the widget (room for axis labels)
    def _plot(self) -> QRectF:
        base = QRectF(66, 14, max(10, self.width() - 66 - 18), max(10, self.height() - 14 - 46))
        if self.true_scale and self.series and self._has_data():
            # True scale: the box itself gets the real shape (same metres per pixel across and up),
            # so a long, low line gives a short, wide box and the height axis never shows empty
            # heights below the ground. A very steep short line is kept within the normal box.
            lo, hi = self._data_range()
            total_m = max(max((s["res"].get("total_distance_m") or 1.0) for s in self.series), 1e-9)
            h = base.width() * (hi - lo) / total_m
            h = min(base.height(), max(14.0, h))
            return QRectF(base.left(), base.top() + (base.height() - h) / 2, base.width(), h)
        return base

    def _range(self):
        return self._data_range()

    def _xy(self, res: dict, i: int, lo: float, hi: float):
        plot, dist, total = self._plot(), res["distance"], self._total()
        z = res["elevation"][i]
        x = plot.left() + dist[i] / total * plot.width()
        y = None if z is None else plot.bottom() - (z - lo) / (hi - lo) * plot.height()
        return x, y

    def mousePressEvent(self, e) -> None:
        for rect, idx in self._legend_rects:
            if rect.contains(e.position()):
                self.profileClicked.emit(idx)
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        over = any(r.contains(e.position()) for r, _i in self._legend_rects)
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)
        if not self.series:
            return
        plot = self._plot()
        frac = (e.position().x() - plot.left()) / plot.width()
        self._hover = frac * self._total() if 0 <= frac <= 1 else None
        self.update()

    def leaveEvent(self, e) -> None:
        self._hover = None
        self.update()

    @staticmethod
    def _nice_ticks(lo: float, hi: float, target: int):
        """Round tick values (1, 2, 2.5, 5 x 10^n) between lo and hi, and how many decimals they need."""
        import math
        span = max(hi - lo, 1e-12)
        raw = span / max(target, 1)
        mag = 10 ** math.floor(math.log10(raw))
        step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag * (1 + 1e-9))
        decimals = 0
        while abs(step * 10 ** decimals - round(step * 10 ** decimals)) > 1e-9 and decimals < 4:
            decimals += 1
        v = math.ceil(lo / step - 1e-9) * step
        ticks = []
        while v <= hi + step * 1e-9:
            ticks.append(v)
            v += step
        return ticks, decimals

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        self._legend_rects = []
        plot = self._plot()
        if not self.series or not self._has_data():
            p.setPen(QPen(QColor("#dde2e7"), 1))
            p.drawRect(plot)
            p.setPen(QColor("#6b737b"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter,
                       "No elevation data under this line." if self.series else "Draw a line on the map.")
            return
        multi = len(self.series) > 1
        lo, hi = self._range()
        total = self._total()
        unit = self.series[-1]["res"].get("distance_units", "m")
        small = QFont(self.font())
        small.setPointSizeF(8)
        p.setFont(small)
        axis_ink, grid = QColor("#5b6670"), QColor("#eef1f4")

        # grid and tick labels at round numbers
        y_ticks, y_dec = self._nice_ticks(lo, hi, max(2, int(plot.height() // 42)))
        last_y = None
        for v in y_ticks:
            y = plot.bottom() - (v - lo) / (hi - lo) * plot.height()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            if last_y is None or abs(last_y - y) >= 13:
                p.setPen(axis_ink)
                p.drawText(QRectF(0, y - 8, plot.left() - 6, 16),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{v:,.{y_dec}f}")
                last_y = y
        x_ticks, x_dec = self._nice_ticks(0.0, total, max(2, int(plot.width() // 60)))
        for v in x_ticks:
            x = plot.left() + v / total * plot.width()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            p.setPen(axis_ink)
            p.drawText(QRectF(x - 30, plot.bottom() + 4, 60, 14), Qt.AlignmentFlag.AlignHCenter, f"{v:,.{x_dec}f}")
        p.setPen(QPen(QColor("#cfd6dc"), 1))             # only the left and bottom edges, no heavy box
        p.drawLine(plot.bottomLeft(), plot.bottomRight())
        p.drawLine(plot.topLeft(), plot.bottomLeft())

        # axis titles say what the numbers mean
        title_font = QFont(self.font())
        title_font.setPointSizeF(8.5)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(axis_ink)
        x_title = (f"Distance along the line ({unit})" if not multi else f"Distance along each line ({unit})") \
            + ("  \u00b7  true scale: 1 m up = 1 m across" if self.true_scale else "")
        p.drawText(QRectF(plot.left() - 40, plot.bottom() + 22, plot.width() + 40, 16), Qt.AlignmentFlag.AlignCenter, x_title)
        p.save()
        p.translate(11, plot.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-90, -9, 180, 18), Qt.AlignmentFlag.AlignCenter, "Elevation (m)")
        p.restore()
        p.setFont(small)

        # for every profile: filled area under the line, then the line (a gap in the data breaks the line)
        for ser in self.series:
            res, col = ser["res"], QColor(ser["color"])
            runs, run = [], []
            for i in range(len(res["elevation"])):
                x, y = self._xy(res, i, lo, hi)
                if y is None:
                    if run:
                        runs.append(run)
                    run = []
                else:
                    run.append(QPointF(x, y))
            if run:
                runs.append(run)
            for r in runs:
                poly = QPolygonF(r + [QPointF(r[-1].x(), plot.bottom()), QPointF(r[0].x(), plot.bottom())])
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 26 if multi else 46))
                p.drawPolygon(poly)
                p.setBrush(Qt.BrushStyle.NoBrush)
                chosen = multi and ser.get("idx") == self.selected
                p.setPen(QPen(col, 3.0 if chosen else (1.5 if multi else 1.8), Qt.PenStyle.SolidLine,
                              Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                p.drawPolyline(QPolygonF(r))

        # the two ends of each line: A and B for one profile, a coloured dot at each end for several
        letter_font = QFont(self.font())
        letter_font.setPointSizeF(7.5)
        letter_font.setBold(True)
        for ser in self.series:
            res = ser["res"]
            pts = [(i, self._xy(res, i, lo, hi)) for i in range(len(res["elevation"]))]
            pts = [(i, xy) for i, xy in pts if xy[1] is not None]
            if not pts:
                continue
            if multi:
                for _i, (x, y) in (pts[0], pts[-1]):
                    p.setPen(QPen(QColor("#ffffff"), 1.5))
                    p.setBrush(QColor(ser["color"]))
                    p.drawEllipse(QPointF(x, y), 5, 5)
            else:
                for letter, (_i, (x, y)) in (("A", pts[0]), ("B", pts[-1])):
                    p.setPen(QPen(QColor("#ffffff"), 1.5))
                    p.setBrush(QColor("#1b2530"))
                    p.drawEllipse(QPointF(x, y), 7, 7)
                    p.setFont(letter_font)
                    p.setPen(QColor("#ffffff"))
                    p.drawText(QRectF(x - 7, y - 7, 14, 14), Qt.AlignmentFlag.AlignCenter, letter)

        # legend: which colour is which profile
        if multi:
            p.setFont(small)
            lx, ly = plot.left() + 8, plot.top() + 4
            w = 24 + max(p.fontMetrics().horizontalAdvance(s["name"]) for s in self.series) + 10
            box = QRectF(lx - 4, ly - 2, w, 15 * len(self.series) + 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 215))
            p.drawRoundedRect(box, 4, 4)
            bold = QFont(small)
            bold.setBold(True)
            for k, ser in enumerate(self.series):
                y = ly + 15 * k + 7
                chosen = ser.get("idx") == self.selected
                row = QRectF(lx - 4, y - 7.5, w, 15)
                self._legend_rects.append((row, ser.get("idx", k)))
                if chosen:                                  # the profile whose numbers are shown below
                    c = QColor(ser["color"])
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(c.red(), c.green(), c.blue(), 40))
                    p.drawRoundedRect(row, 3, 3)
                p.setPen(QPen(QColor(ser["color"]), 4 if chosen else 3))
                p.drawLine(QPointF(lx, y), QPointF(lx + 14, y))
                p.setPen(QColor("#1b2530"))
                p.setFont(bold if chosen else small)
                p.drawText(QRectF(lx + 20, y - 7, w, 14), Qt.AlignmentFlag.AlignVCenter, ser["name"])
            p.setFont(small)

        if self._hover is not None:
            hx = plot.left() + self._hover / total * plot.width()
            p.setFont(small)
            p.setPen(QPen(QColor("#8a949c"), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(hx, plot.top()), QPointF(hx, plot.bottom()))
            lines = []
            for ser in self.series:
                res = ser["res"]
                dist = res["distance"]
                if self._hover > (dist[-1] or 0.0) + 1e-9:          # this line is shorter than the mouse position
                    continue
                i = min(range(len(dist)), key=lambda k: abs(dist[k] - self._hover))
                x, y = self._xy(res, i, lo, hi)
                if y is None:
                    continue
                p.setPen(QPen(QColor("#ffffff"), 1.5))
                p.setBrush(QColor(ser["color"]) if multi else QColor("#c2571a"))
                p.drawEllipse(QPointF(x, y), 4, 4)
                z = res["elevation"][i]
                lines.append((ser["color"], f"{z:,.1f} m  at  {dist[i]:,.2f} {unit}" if not multi
                              else f"{ser['name']}: {z:,.1f} m  at  {dist[i]:,.2f} {unit}"))
            if lines:
                bw = 186 if not multi else 250
                bh = 18 * len(lines) if not multi else 18 * len(lines) + 2
                box_y = plot.top() + 4 if plot.height() >= 60 + bh else plot.top() - bh - 6
                if multi:
                    box_y = max(box_y, plot.top() + 15 * len(self.series) + 10) if plot.height() >= 60 + bh else box_y
                box = QRectF(min(hx + 8, plot.right() - bw - 4), box_y, bw, bh)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(37, 42, 47, 220))
                p.drawRoundedRect(box, 4, 4)
                for k, (colr, text) in enumerate(lines):
                    row = QRectF(box.left() + 14, box.top() + 1 + 18 * k, bw - 18, 18)
                    if multi:
                        p.setBrush(QColor(colr))
                        p.drawEllipse(QPointF(box.left() + 8, row.center().y()), 3.5, 3.5)
                    p.setPen(QColor("#ffffff"))
                    p.drawText(row if multi else box, Qt.AlignmentFlag.AlignCenter if not multi else
                               Qt.AlignmentFlag.AlignVCenter, text)


class ProfileWindow(QDialog):
    """Floating Elevation Profile box: the height along the clicked line, with min, max, climb and slope."""
    unitsChanged = pyqtSignal(str)
    scaleChanged = pyqtSignal()
    selectionChanged = pyqtSignal(int)      # the profile whose numbers are shown (0, 1, 2 ...)
    closed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("measureWindow")
        self.setWindowTitle("Elevation Profile")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        self.setStyleSheet(MeasureWindow.style())
        self.res: dict | None = None
        self.profiles: dict[int, dict] = {}      # line number (0, 1, ...) -> its profile result; all are drawn together
        self.unit_key: dict[int, str] = {}       # line number -> the distance units its result was measured in
        self.selected: int | None = None         # the profile whose numbers are shown under the graph
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("measureCard")
        body = QVBoxLayout(card)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(6)

        body.addWidget(_card_title("Elevation Profile"))
        top = QHBoxLayout()
        units_label = QLabel("Distance units")
        units_label.setObjectName("measureName")
        self.units = QComboBox()
        for text, key in MeasureWindow.UNITS:
            self.units.addItem(text, key)
        self.units.setCurrentIndex(max(0, self.units.findData(_saved_unit("distance_unit", MeasureWindow.DEFAULT_UNIT))))
        self.units.currentIndexChanged.connect(lambda _i: self.unitsChanged.emit(self.units.currentData()))
        self.true_scale = QCheckBox("True scale (no vertical exaggeration)")
        self.true_scale.setObjectName("measureName")
        self.true_scale.toggled.connect(lambda _c: self._redraw())
        top.addWidget(units_label)
        top.addWidget(self.units)
        graph_label = QLabel("Graph")
        graph_label.setObjectName("measureName")
        self.graph_mode = QComboBox()                      # one combined graph, or one graph per profile
        self.graph_mode.addItem("All together", "together")
        self.graph_mode.addItem("Separate", "separate")
        self.graph_mode.currentIndexChanged.connect(lambda _i: self._redraw())
        top.addWidget(graph_label)
        top.addWidget(self.graph_mode)
        top.addStretch(1)
        if SHOW_TRUE_SCALE:
            top.addWidget(self.true_scale)
        body.addLayout(top)

        self.layer = QLabel("")
        self.layer.setObjectName("measureLayer")
        self.rows: dict[str, QLabel] = {}
        self.hero = QWidget()                      # the length is the headline number
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(0, 2, 0, 0)
        hero_row.setSpacing(8)
        self.rows["length"] = QLabel("")
        self.rows["length"].setObjectName("measureHero")
        self.method = QLabel("Length")
        self.method.setObjectName("measureCaption")
        hero_row.addWidget(self.rows["length"])
        hero_row.addWidget(self.method, 0, Qt.AlignmentFlag.AlignBottom)
        hero_row.addStretch(1)
        body.addWidget(self.hero)

        self.chart = ProfileChart()
        self.chart.profileClicked.connect(self.select)
        body.addWidget(self.chart)
        self.sep_box = QWidget()                           # separate mode: one small graph per profile
        self.sep_layout = QVBoxLayout(self.sep_box)
        self.sep_layout.setContentsMargins(0, 0, 0, 0)
        self.sep_layout.setSpacing(8)
        self.sep_scroll = QScrollArea()
        self.sep_scroll.setWidgetResizable(True)
        self.sep_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sep_scroll.setMinimumHeight(300)
        self.sep_scroll.setMaximumHeight(460)
        self.sep_scroll.setWidget(self.sep_box)
        self.sep_scroll.hide()
        body.addWidget(self.sep_scroll)
        self.pick_hint = QLabel("Click a profile name in the graph (or Ctrl+click its line on the map) to see its numbers.")
        self.pick_hint.setObjectName("measureCaption")
        self.pick_hint.setWordWrap(True)
        body.addWidget(self.pick_hint)

        self.result_box = QWidget()
        grid = QGridLayout(self.result_box)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(5)
        fields = (("min", "Lowest"), ("max", "Highest"), ("start", "Start height (A)"), ("end", "End height (B)"),
                  ("gain", "Total climb"), ("loss", "Total descent"))
        for n, (key, name) in enumerate(fields):
            a = QLabel(name)
            a.setObjectName("measureName")
            b = QLabel("")
            b.setObjectName("measureValue")
            b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(a, n // 2, (n % 2) * 2)
            grid.addWidget(b, n // 2, (n % 2) * 2 + 1)
            self.rows[key] = b
        self.note = QLabel("")
        self.note.setObjectName("measureNote")
        self.note.setWordWrap(True)
        body.addWidget(self.result_box)
        body.addWidget(self.note)
        outer.addWidget(card)
        self.show_waiting()

    def set_layer(self, name: str, geographic: bool) -> None:
        self.method.setText("Length")
        self.layer.setText(name)

    def clear_profiles(self) -> None:
        """A new Elevation Profile session: forget every earlier line."""
        self.profiles.clear()
        self.unit_key.clear()
        self.selected = None

    def show_waiting(self, text: str = "Click the first point of the line on the map.", idx: int | None = None) -> None:
        """idx = the line being drawn that has no result yet; the other lines stay on the graph."""
        if idx is not None:
            self.profiles.pop(idx, None)
        else:
            self.profiles.clear()
        if self.profiles:
            self._show_latest()
            return
        self.res = None
        self.chart.set_result(None, False)
        self.hero.hide()
        self.result_box.hide()
        self.note.hide()
        self.adjustSize()

    def _redraw(self) -> None:
        series = [{"res": r, "color": PROFILE_COLORS[i % len(PROFILE_COLORS)], "name": f"Profile {i + 1}", "idx": i}
                  for i, r in sorted(self.profiles.items())]
        separate = self.graph_mode.currentData() == "separate" and len(series) > 1
        self.chart.set_series(series, self.true_scale.isChecked(), self.selected)
        self.chart.setVisible(not separate)
        self.sep_scroll.setVisible(separate)
        self.pick_hint.setVisible(len(self.profiles) > 1 and not separate)
        if separate:
            self._fill_separate(series)
        self.adjustSize()

    def _fill_separate(self, series: list[dict]) -> None:
        """One graph per profile, each with its own height scale and its own numbers."""
        while self.sep_layout.count():
            item = self.sep_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for s in series:
            res, idx = s["res"], s["idx"]
            u = res.get("distance_units", "m")

            def m(v):
                return "\u2013" if v is None else f"{v:,.1f} m"
            head = QLabel(f"<span style='color:{s['color']}'>\u25cf</span> <b>{s['name']}</b> \u00b7 "
                          f"{res['total_distance']:,.3f} {u} \u00b7 lowest {m(res.get('min'))} \u00b7 "
                          f"highest {m(res.get('max'))} \u00b7 climb {m(res.get('gain'))} \u00b7 "
                          f"descent {m(res.get('loss'))}")
            head.setObjectName("measureName")
            head.setWordWrap(True)
            chart = ProfileChart()
            chart.setMinimumSize(470, 190)
            chart.set_series([s], self.true_scale.isChecked(), None)
            self.sep_layout.addWidget(head)
            self.sep_layout.addWidget(chart)
        self.sep_layout.addStretch(1)

    def _show_latest(self) -> None:
        """The numbers under the graph belong to the newest line; the graph shows all of them."""
        self._set_selected(max(self.profiles))

    def show_result(self, res: dict, finished: bool, idx: int = 0) -> None:
        """A profile was measured: its numbers are shown (click another name in the graph to see that one)."""
        self.profiles[idx] = res
        self._set_selected(idx)

    def select(self, idx: int) -> None:
        if idx in self.profiles:
            self._set_selected(idx)

    def _set_selected(self, idx: int) -> None:
        self.selected = idx
        self._redraw()
        self._fill_stats(idx)
        self.selectionChanged.emit(idx)

    def _fill_stats(self, idx: int) -> None:
        res = self.profiles[idx]
        self.res = res
        u = res.get("distance_units", "m")
        n = len(self.profiles)
        dot = f"<span style='color:{PROFILE_COLORS[idx % len(PROFILE_COLORS)]}'>\u25cf</span> " if n > 1 else ""
        self.method.setText(f"{dot}Profile {idx + 1} length" if n > 1 else "Length")

        def m(v, suffix=" m"):
            return "–" if v is None else f"{v:,.1f}{suffix}"
        self.rows["length"].setText(f"{res['total_distance']:,.3f} {u}")
        self.rows["min"].setText(m(res.get("min")))
        self.rows["max"].setText(m(res.get("max")))
        self.rows["gain"].setText(m(res.get("gain")))
        self.rows["loss"].setText(m(res.get("loss")))
        self.rows["start"].setText(m(res.get("start_elevation")))
        self.rows["end"].setText(m(res.get("end_elevation")))
        outside = res.get("samples_outside", 0)
        self.note.setText(f"{outside} of {len(res['elevation'])} sample points are outside the DEM or have no data."
                          if outside else "")
        self.note.setVisible(bool(outside))
        self.hero.show()
        self.result_box.show()
        self.adjustSize()

    def closeEvent(self, e) -> None:
        self.closed.emit()
        super().closeEvent(e)

    def reject(self) -> None:           # Esc or the close button
        self.close()



# Measure-window tips (Distance, Area, Profile) are shown only until the first measurement of each kind is finished.
_HINTS_SEEN: set = set()

# Surface (3D) area is switched off for now: the Area window shows only the 2D numbers (Area and
# Perimeter), which are the ones checked against ArcMap. The 3D code is all still here (backend
# core/measure/surface_area.py, the "include_surface" request field and the two extra rows in
# AreaWindow.show_result). We may add it back in future: set this to True and restart the backend.
SHOW_SURFACE_AREA = False

# The "True scale" tick of the Elevation Profile is hidden for now (the chart code still supports it).
# Set this to True to bring the checkbox back.
SHOW_TRUE_SCALE = False

class AreaWindow(QDialog):
    """Floating Area box: the Area and Perimeter of the polygon being clicked, with a units menu."""
    unitsChanged = pyqtSignal(str)          # backend unit name: square metres, hectares ...
    closed = pyqtSignal()

    UNITS = [("Square metres", "square metres"), ("Hectares", "hectares"),
             ("Square kilometres", "square kilometres"), ("Acres", "acres"), ("Square miles", "square miles")]
    DEFAULT_UNIT = "square kilometres"
    DECIMALS = {"m\u00b2": 1, "ha": 2, "km\u00b2": 3, "ac": 2, "mi\u00b2": 3}

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("measureWindow")
        self.setWindowTitle("Measure Area")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setModal(False)
        self.setMinimumWidth(310)
        self.setStyleSheet(MeasureWindow.style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("measureCard")
        body = QVBoxLayout(card)
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(5)

        body.addWidget(_card_title("Area"))
        top = QHBoxLayout()
        units_label = QLabel("Units")
        units_label.setObjectName("measureName")
        self.units = QComboBox()
        for text, key in self.UNITS:
            self.units.addItem(text, key)
        self.units.setCurrentIndex(max(0, self.units.findData(_saved_unit("area_unit", self.DEFAULT_UNIT))))
        self.units.currentIndexChanged.connect(lambda _i: self.unitsChanged.emit(self.units.currentData()))
        top.addWidget(units_label)
        top.addWidget(self.units, 1)
        body.addLayout(top)

        self.method = QLabel("Area measurement")
        self.method.setObjectName("measureMethod")
        self.layer = QLabel("")
        self.layer.setObjectName("measureLayer")
        self.hint = QLabel("Click the first corner on the map.")
        self.hint.setObjectName("measureHint")
        self.hint.setWordWrap(True)
        body.addWidget(self.hint)

        self.rows: dict[str, QLabel] = {}
        self.names: dict[str, QLabel] = {}
        self.result_box = QWidget()
        rl = QVBoxLayout(self.result_box)
        rl.setContentsMargins(0, 4, 0, 0)
        rl.setSpacing(3)
        for key, name, big in (("area", "Area", True), ("perimeter", "Perimeter", False),
                                ("surface", "Surface area (3D)", False), ("extra", "Extra from slope", False)):
            line = QHBoxLayout()
            a = QLabel(name + ":")
            a.setObjectName("measureName")
            b = QLabel("")
            b.setObjectName("measureBig" if big else "measureValue")
            b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line.addWidget(a)
            line.addStretch(1)
            line.addWidget(b)
            rl.addLayout(line)
            self.rows[key] = b
            self.names[key] = a
        body.addWidget(self.result_box)
        self.history = MeasureHistory("areas")
        body.addWidget(self.history)
        outer.addWidget(card)
        self.show_waiting()

    def set_layer(self, name: str, geographic: bool) -> None:
        self.method.setText("Area")
        self.layer.setText(name)

    def show_waiting(self, text: str = "Click the first corner on the map.") -> None:
        self.hint.setText(text)
        self.hint.setVisible(type(self).__name__ not in _HINTS_SEEN)
        self.result_box.hide()
        self.adjustSize()

    def show_result(self, res: dict, finished: bool) -> None:
        self.hint.setText("Double-click to finish \u00b7 Right-click removes the last point" if not finished
                          else "Area finished. Click the map to measure a new area.")
        self.hint.setVisible(type(self).__name__ not in _HINTS_SEEN)
        if finished:
            _HINTS_SEEN.add(type(self).__name__)       # the tips are shown once, then stay out of the way
        d = self.DECIMALS.get(res["unit"], 2)
        self.rows["area"].setText(f"{res['area']:,.{d}f} {res['unit']}")
        pd = 3 if res["perimeter_unit"] == "km" else 1
        self.rows["perimeter"].setText(f"{res['perimeter']:,.{pd}f} {res['perimeter_unit']}")
        surf = res.get("surface")
        for key in ("surface", "extra"):                  # 3D area is worked out once the polygon is finished
            self.rows[key].setVisible(surf is not None)
            self.names[key].setVisible(surf is not None)
        if surf is not None:
            self.rows["surface"].setText(f"{surf['surface_area']:,.{d}f} {res['unit']}")
            ratio = surf.get("surface_to_flat_ratio")
            self.rows["extra"].setText("\u2013" if ratio is None else f"+{(ratio - 1) * 100:,.1f} %")
        self.result_box.show()
        self.adjustSize()

    def closeEvent(self, e) -> None:
        self.closed.emit()
        super().closeEvent(e)

    def reject(self) -> None:           # Esc or the close button
        self.close()


# ----------------------------------------------------------------------------
# main window
# ----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        set_settings_provider(lambda: self.api_get("/file/project/settings"))   # tools open with the project defaults
        self.setWindowTitle(f"{PROJECT_TITLE} - {APP_NAME}")  
        icon_path = Path(__file__).resolve().parent / "assets" / "gtaam_tool_icon.png"
        self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1480, 900)
        self.setMinimumSize(1040, 660)

        self.ws = SampleWorkspace()
        self.selected: str | None = None
        self.project_path: Path | None = None
        self.project_name = PROJECT_TITLE
        self.flags = {"contents": True, "statistics": False, "pixel_inspector": True,
                      "north_arrow": True, "scale_bar": True, "map_label": True,
                      "annotation": False}
        self._saved_sizes = [290, 900, 330]
        self._pixel_pool = QThreadPool(self)
        self._pixel_pool.setMaxThreadCount(1)
        self._pixel_request_in_flight = False
        self._pending_pixel_request: tuple[str, int, int] | None = None
        self._pixel_workers: set[_PixelSampleWorker] = set()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_tabbar())
        self.ribbon = RibbonBar(self.is_on, self.is_available)
        self.ribbon.toolTriggered.connect(self.run_tool)
        root.addWidget(self.ribbon)
        root.addWidget(self._build_workspace(), 1)
        root.addWidget(self._build_statusbar())

        # overlays that float above everything
        self.toast = QLabel("", central)
        self.toast.setObjectName("toast")
        self.toast.hide()
        self._toast_timer = QTimer(self, singleShot=True)
        self._toast_timer.timeout.connect(self.toast.hide)

        QShortcut(QKeySequence("F11"), self, activated=self.act_fullscreen)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.act_save_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.act_open_project)
        QShortcut(QKeySequence("Esc"), self, activated=self._escape)

        self._connect_signals()
        self._autosave_ticks = 0                           # Project Settings > Project > Auto-save
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._autosave_timer.start(60_000)                 # once a minute
        self.select_tab(DEFAULT_TAB)
        self.on_layer_selected(None)
        QTimer.singleShot(0, self.map.canvas.fit)
        self._init_project_actions()


    # ----- construction -----------------------------------------------------
    def _update_window_title(self) -> None:
        self.setWindowTitle(f"{self.project_name} - {APP_NAME}")

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._style_native_titlebar()

    def _style_native_titlebar(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = wintypes.HWND(int(self.winId()))

            def put(attr: int, value: int) -> None:
                v = ctypes.c_int(value)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

            rgb = lambda r, g, b: r | (g << 8) | (b << 16)
            put(20, 0)                          # light mode: min/max/close icons dark ho jayenge
            put(35, rgb(0xF8, 0xF9, 0xFA))      # title bar colour (tab bar #e9ecef)
            put(36, rgb(0x21, 0x25, 0x29))      # title text colour
            put(34, rgb(0xCE, 0xD4, 0xDA))      # window border colour
        except Exception:
            pass

    def _build_tabbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("tabbar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 0, 14, 0)
        h.setSpacing(2)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons: dict[str, QPushButton] = {}
        for mod in TAB_MODULES:
            b = QPushButton(mod.TAB)
            b.setObjectName("tabButton")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=mod.TAB: self.select_tab(name))
            self.tab_group.addButton(b)
            self.tab_buttons[mod.TAB] = b
            h.addWidget(b)
        h.addStretch(1)

        bar.setFixedHeight(46)
        return bar

    def _build_workspace(self) -> QWidget:
        self.contents = ContentsPane(self.ws)
        self.map = MapSection(self.ws)
        self.inspector = InspectorPane(self.ws)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(5)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.contents)
        self.splitter.addWidget(MapBox(self.map))
        self.splitter.addWidget(self.inspector)
        self.contents.setMinimumWidth(230)
        self.inspector.setMinimumWidth(270)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes(self._saved_sizes)
        self.inspector.setVisible(False)          # statistics open only when asked for (ribbon or the Statistics button)
        self.map.set_pane_buttons(self.flags["contents"], False)
        return self.splitter

    def _build_statusbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("statusbar")
        bar.setFixedHeight(28)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.addStretch(1)
        lay.addWidget(BackendStatus())
        return bar

    def _connect_signals(self) -> None:
        c, m, i = self.contents, self.map, self.inspector
        c.layerSelected.connect(self.on_layer_selected)
        c.visibilityChanged.connect(self.set_layer_visible)
        c.statisticsRequested.connect(lambda lid: self._show_stats_for(lid))
        c.zoomToLayerRequested.connect(self.map.canvas.zoom_to_layer)
        c.attributeTableRequested.connect(self._open_attribute_table)
        c.removeRequested.connect(self._remove_layer)
        c.layerRenamed.connect(self._rename_layer)
        c.layersReordered.connect(self._layers_reordered)
        c.opacityChanged.connect(self._menu_opacity_changed)
      
        c.closeRequested.connect(lambda: self.set_flag("contents", False))
    
        i.closeRequested.connect(lambda: self.set_flag("statistics", False))
        i.showStatsRequested.connect(self.act_show_stats)
        i.opacityChanged.connect(self._opacity_changed)
        i.toolRun.connect(self.on_tool_run)
        i.toolCancelled.connect(self.act_show_stats)
        m.layersToggled.connect(lambda: self.toggle("contents"))
        m.statisticsToggled.connect(lambda: self.toggle("statistics"))
        m.discardPreview.connect(self.act_discard_preview)
        m.canvas.regionsChanged.connect(self._regions_changed)
        m.canvas.measureChanged.connect(self._measure_changed)
        m.canvas.measureShapeRemoved.connect(self._measure_shape_removed)
        m.canvas.measuresCleared.connect(self._measure_cards_cleared)
        m.canvas.shapeClicked.connect(self._profile_shape_clicked)
        m.canvasAdded.connect(self.ws.add_canvas)
        m.canvasSwitched.connect(self._canvas_switched)
        m.canvasClosed.connect(self.ws.remove_canvas)
        m.canvasRenamed.connect(self.ws.rename_canvas)
        m.layerDropped.connect(self._layer_dropped)
        m.canvas.modeChanged.connect(self._mode_changed)
        m.canvas.statusMessage.connect(self.set_status)
        m.pixelSampleRequested.connect(self._request_pixel_sample)

    # ----- tabs / search ----------------------------------------------------
    def select_tab(self, name: str) -> None:
        for mod in TAB_MODULES:
            if mod.TAB == name:
                self.tab_buttons[name].setChecked(True)
                self.ribbon.show_tab(mod)
                self.current_tab = name
                return

    def _escape(self) -> None:
        self.map.canvas.cancel_draw()


    # ----- feedback ---------------------------------------------------------
    def show_toast(self, text: str, ms: int = 3000) -> None:
        self.toast.setText(text)
        self.toast.adjustSize()
        c = self.centralWidget()
        self.toast.move((c.width() - self.toast.width()) // 2, c.height() - self.toast.height() - 48)
        self.toast.show()
        self.toast.raise_()
        self._toast_timer.start(ms)

    def set_status(self, text: str) -> None:
        pass

    def api_post(self, path: str, payload: dict | None = None) -> dict:
        wait_until_ready()

        url = f"{BASE_URL}{API_PREFIX}{path}"

        try:
            response = httpx.post(
             url,
                json=payload or {},
                timeout=60
        )

            response.raise_for_status()

            if not response.content:
                raise RuntimeError(
                f"Backend returned an empty response for {url}"
            )

            try:
                data = response.json()
            except ValueError as e:
                raise RuntimeError(
                f"Backend returned invalid JSON: {response.text}"
            ) from e

            if not isinstance(data, dict):
                raise RuntimeError(
                f"Expected a JSON object, received: {data}"
            )

            return data

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
            f"API error {e.response.status_code}: "
            f"{e.response.text}"
        ) from e

        except httpx.RequestError as e:
            raise RuntimeError(
            f"Backend connection failed: {e}"
        ) from e


    def api_put(self, path: str, payload: dict | None = None) -> dict:
        wait_until_ready()
        url = f"{BASE_URL}{API_PREFIX}{path}"
        try:
            response = httpx.put(url, json=payload or {}, timeout=60)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Backend connection failed: {e}") from e

    def api_get(self, path: str, params: dict | None = None) -> dict:
        wait_until_ready()
        url = f"{BASE_URL}{API_PREFIX}{path}"
        try:
            response = httpx.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Backend connection failed: {e}") from e

    def api_get_bytes(self, path: str) -> bytes:
        wait_until_ready()
        url = f"{BASE_URL}{API_PREFIX}{path}"
        try:
            response = httpx.get(url, timeout=60)
            response.raise_for_status()
            if not response.content:
                raise RuntimeError(f"Backend returned an empty response for {url}")
            return response.content
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Backend connection failed: {e}") from e

    def _request_pixel_sample(self, layer_id: str, row: int, col: int) -> None:
        request = (layer_id, row, col)
        if self._pixel_request_in_flight:
            self._pending_pixel_request = request
            return
        self._start_pixel_sample(request)

    def _start_pixel_sample(self, request: tuple[str, int, int]) -> None:
        layer_id, row, col = request
        worker = _PixelSampleWorker(layer_id, row, col)
        self._pixel_workers.add(worker)
        self._pixel_request_in_flight = True
        worker.signals.finished.connect(self._pixel_sample_finished)
        self._pixel_pool.start(worker)

    def _pixel_sample_finished(self, worker: _PixelSampleWorker, result: object) -> None:
        self._pixel_workers.discard(worker)
        self._pixel_request_in_flight = False
        is_current = (
            self.selected == worker.layer_id
            and self.map.is_pixel_sample_current(worker.layer_id, worker.row, worker.col)
        )
        if isinstance(result, Exception):
            if is_current:
                self.map.show_pixel_error(worker.layer_id, str(result))
        elif not isinstance(result, dict):
            if is_current:
                self.map.show_pixel_error(worker.layer_id, "Backend returned invalid pixel data.")
        else:
            self.map.cache_pixel_sample(worker.layer_id, worker.row, worker.col, result)
            if is_current:
                self.map.update_backend_pixel(worker.layer_id, result)

        pending = self._pending_pixel_request
        self._pending_pixel_request = None
        if pending is not None and self.map.is_pixel_sample_current(*pending):
            self._start_pixel_sample(pending)

    @staticmethod
    def _decode_raster_image(content: bytes) -> np.ndarray:
        image = QImage()
        if not image.loadFromData(content):
            raise RuntimeError("Backend returned an image that could not be decoded.")
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        bits = image.bits()
        bits.setsize(image.sizeInBytes())
        return np.frombuffer(bits, dtype=np.uint8).reshape(
            image.height(), image.width(), 4
        ).copy()

    # ----- tool dispatch ----------------------------------------------------
    def raster_names(self) -> list[str]:
        return [l.name for l in self.ws.rasters()]

    def run_tool(self, tool: dict) -> None:
        kind = tool.get("kind", "toast")
        self.set_status(tool["label"])
        if kind == "action":
            fn = getattr(self, "act_" + tool["action"], None)
            if fn is None:
                self.show_toast(f"{tool['label']}: backend not connected in this interface preview")
            else:
                try:
                    fn()
                except Exception as e:
                    self.show_toast(f"{tool['label']}: error occurred while running the tool")
        elif kind == "toggle":
            self.toggle(tool["toggle"])
        elif kind == "panel":
            self.set_flag("statistics", True)
            wired = bool(tool.get("handler")) and hasattr(self, "run_" + tool["handler"]) or tool.get("handler") == "terrain_derivative"
            self.inspector.show_tool(tool, self.raster_names(), wired)
        elif kind == "dialog":
            dlg = ToolDialog(self, tool, self.raster_names())
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.on_tool_run(tool, dlg.form.values())
        else:
            self.show_toast(tool["label"])

    def on_tool_run(self, tool: dict, values: dict) -> None:
        handler = tool.get("handler")
        fn = getattr(self, "run_" + handler, None) if handler else None
        in_panel = bool(getattr(self.inspector, "_busy", False))   # run started from the tool panel button
        if fn:
            try:
                fn(tool, values)
            except Exception as e:
                traceback.print_exc()
                if in_panel:
                    self.inspector.run_finished(False, _friendly_error(e))
                else:
                    self.show_toast(f"{tool['label']}: {e}")
                return
            if in_panel:
                self.inspector.run_finished(True, "Result is ready.")
            self.set_status(tool["label"])
        else:
            msg = "This tool is not connected to the backend yet."
            if in_panel:
                self.inspector.run_finished(False, msg)
            else:
                self.show_toast(f"{tool['label']}: {msg}")
            self.set_status(f"{tool['label']} (preview)")

    # handlers for tools that have a visible effect in the frontend
    # ----- Analysis > Quality & Statistics: ask the backend, show the answer ------
    def run_histogram(self, tool: dict, values: dict) -> None:
        src = _quality_source(self, values)
        res = self.api_get(f"/analysis/quality-statistics/histogram/{src.id}",
                           {"bins": int(values.get("bins", 30))})
        if not res.get("counts"):
            self.show_toast("Histogram: the layer has no valid pixels")
            return
        self._histogram_dialog = HistogramDialog(self, src.name, res, bool(values.get("logarithmic_counts", False)))
        self._histogram_dialog.show()
        self.set_status(f"Histogram · {src.name} · {res['pixels']:,} pixels")

    def run_nodata_check(self, tool: dict, values: dict) -> None:
        src = _quality_source(self, values)
        r = self.api_get(f"/analysis/quality-statistics/nodata-check/{src.id}")
        self._nodata_dialog = NoDataDialog(self, src.name, r, src.source_width, src.source_height)
        self._nodata_dialog.show()
        self.set_status(f"NoData Check \u00b7 {src.name} \u00b7 {r['percent']}% NoData")

    def run_outlier_check(self, tool: dict, values: dict) -> None:
        src = _quality_source(self, values)
        method = "zscore" if str(values.get("method", "")).lower().startswith("z") else "iqr"
        thr = float(values.get("threshold", 1.5 if method == "iqr" else 3.0))
        r = self.api_get(f"/analysis/quality-statistics/outlier-check/{src.id}",
                         {"method": method, "threshold": thr})
        self._outlier_dialog = OutlierDialog(self, src.name, r, method)
        self._outlier_dialog.show()
        self.set_status(f"Outlier Check \u00b7 {src.name} \u00b7 {r['outlier_count']:,} outliers")

    def run_ramp(self, tool: dict, values: dict) -> None:
        self.ws.apply_ramp(values["ramp"])
        self.map.canvas.invalidate()
        self.contents.refresh_legend()
        if self.selected:
            self._show_stats_for(self.selected)
        self.show_toast(f"Colour ramp: {values['ramp']}")

    def run_preview_edit(self, tool: dict, values: dict) -> None:
        self.act_preview_edit()

    def run_select_dems(self, tool: dict, values: dict) -> None:
        chosen = values.get("dems", [])
        for lyr in self.ws.rasters():
            if lyr.id in ("dem", "east"):
                self.set_layer_visible(lyr.id, lyr.name in chosen)
                self.contents.set_visible(lyr.id, lyr.name in chosen)
        self.map.canvas.fit()
        self.show_toast(f"{len(chosen)} DEM{'s' if len(chosen) != 1 else ''} selected for the mosaic")

    # ----- Analysis > Measure > Distance: collect clicks on the map, ask the backend ------
    def _measure_source(self):
        """The DEM to measure on: the selected raster, or the first loaded one."""
        def measurable(l) -> bool:
            return l.group == "raster" and l.user_added and l.data is None and l.rgba is not None
        chosen = next((l for l in self.ws.layers if l.id == self.selected and measurable(l)), None)
        return chosen or next((l for l in self.ws.rasters() if measurable(l)), None)

    def act_measure_distance(self) -> None:
        """Analysis > Distance: open the Measure box and start measuring on the selected DEM (or the first)."""
        source = self._measure_source()
        if source is None:
            self.show_toast("Load a raster DEM before measuring.")
            return
        if getattr(self, "_measure_window", None) is None:
            self._measure_window = MeasureWindow(self)
            self._measure_window.unitsChanged.connect(lambda _u: self._measure_update())
            self._measure_window.closed.connect(self._measure_closed)
            self._wire_history(self._measure_window)
        for other in (getattr(self, "_area_window", None), getattr(self, "_profile_window", None)):
            if other is not None:
                other.hide()
        self._measure_kind = "line"
        self._measure_layer = source
        self._measure_points: list = []
        self._measure_done = False
        w = self._measure_window
        w.set_layer(source.name, "4326" in (source.crs or ""))
        w.history.clear()
        w.show_waiting()
        if not w.isVisible():
            w.move(self.map.mapToGlobal(QPoint(24, 70)))
        w.show()
        w.raise_()
        self.map.canvas.start_measure("line")
        self.map.canvas.keep_measure = w.history.keep.isChecked()
        self.map.canvas.setFocus()

    def act_measure_area(self) -> None:
        """Analysis > Area: open the Area box and click the corners of a polygon on the selected DEM."""
        source = self._measure_source()
        if source is None:
            self.show_toast("Load a raster DEM before measuring.")
            return
        if getattr(self, "_area_window", None) is None:
            self._area_window = AreaWindow(self)
            self._area_window.unitsChanged.connect(lambda _u: self._measure_update())
            self._area_window.closed.connect(self._measure_closed)
            self._wire_history(self._area_window)
        for other in (getattr(self, "_measure_window", None), getattr(self, "_profile_window", None)):
            if other is not None:
                other.hide()
        self._measure_kind = "polygon"
        self._measure_layer = source
        self._measure_points = []
        self._measure_done = False
        w = self._area_window
        w.set_layer(source.name, "4326" in (source.crs or ""))
        w.history.clear()
        w.show_waiting()
        if not w.isVisible():
            w.move(self.map.mapToGlobal(QPoint(24, 70)))
        w.show()
        w.raise_()
        self.map.canvas.start_measure("polygon")
        self.map.canvas.keep_measure = w.history.keep.isChecked()
        self.map.canvas.setFocus()

    def _area_update(self) -> None:
        w = getattr(self, "_area_window", None)
        lyr = getattr(self, "_measure_layer", None)
        points = getattr(self, "_measure_points", [])
        if w is None or lyr is None:
            return
        self._measure_refresh_cards("polygon", lyr, w)
        if len(points) < 3:
            w.show_waiting(("Click the first corner on the map.", "Click the second corner.",
                            "Click the third corner to see the area.")[len(points)])
            return
        pixels = self._canvas_to_pixels(lyr, points)
        try:
            res = self.api_post("/analysis/measure/area", {
                "layer_id": lyr.id, "pixels": pixels, "units": w.units.currentData(),
                "include_surface": SHOW_SURFACE_AREA and bool(self._measure_done)})
        except Exception as e:
            self.show_toast(f"Area: {e}")
            return
        w.show_result(res, self._measure_done)
        if self._measure_done:
            self._measure_record("polygon", res, w)
        self.set_status(f"Area \u00b7 {lyr.name} \u00b7 {res['area']:,.3f} {res['unit']}")

    def act_measure_profile(self) -> None:
        """Analysis > Elevation Profile: draw a line on the selected DEM and see the height along it."""
        source = self._measure_source()
        if source is None:
            self.show_toast("Load a raster DEM before drawing a profile.")
            return
        if getattr(self, "_profile_window", None) is None:
            self._profile_window = ProfileWindow(self)
            self._profile_window.unitsChanged.connect(lambda _u: self._measure_update())
            self._profile_window.closed.connect(self._measure_closed)
            self._profile_window.selectionChanged.connect(self._profile_selected)
        for other in (getattr(self, "_measure_window", None), getattr(self, "_area_window", None)):
            if other is not None:
                other.hide()
        self._measure_kind = "profile"
        self._measure_layer = source
        self._measure_points = []
        self._measure_done = False
        w = self._profile_window
        w.set_layer(source.name, "4326" in (source.crs or ""))
        w.clear_profiles()
        w.show_waiting()
        if not w.isVisible():
            w.move(self.map.mapToGlobal(QPoint(24, 70)))
        w.show()
        w.raise_()
        self.map.canvas.start_measure("line", colored=True)
        self.map.canvas.setFocus()

    def _canvas_to_pixels(self, lyr, points) -> list:
        """Canvas positions -> [row, column] of the layer's own pixels (a layer in another coordinate system is placed by its real position)."""
        display_height, display_width = lyr.rgba.shape[:2]
        place = self.ws.placement(lyr)
        out = []
        for cx, cy in points:
            if place is not None:
                hit = map_geometry.to_layer_pixel(place, cx, cy)
                if hit is not None:
                    cx, cy = hit
            out.append([cy * lyr.source_height / display_height, cx * lyr.source_width / display_width])
        return out

    def _profile_fetch(self, lyr, points: list, units: str) -> dict:
        """Ask the backend for the elevation profile along one clicked line."""
        pixels = self._canvas_to_pixels(lyr, points)
        return self.api_post("/analysis/measure/elevation-profile", {
            "layer_id": lyr.id, "pixels": pixels, "units": units, "samples": 400})

    def _profile_update(self) -> None:
        w = getattr(self, "_profile_window", None)
        lyr = getattr(self, "_measure_layer", None)
        points = getattr(self, "_measure_points", [])
        if w is None or lyr is None:
            return
        canvas = self.map.canvas
        # which line this is: finished lines are kept in canvas.measure_shapes (the one just finished is the last)
        idx = len(canvas.measure_shapes) - 1 if self._measure_done and canvas.measure_shapes else len(canvas.measure_shapes)
        units = w.units.currentData()
        # the distance units were changed: the lines drawn earlier are measured again in the new units
        for k, shape in enumerate(canvas.measure_shapes):
            if k != idx and w.unit_key.get(k) != units:
                try:
                    w.profiles[k] = self._profile_fetch(lyr, shape["pts"], units)
                    w.unit_key[k] = units
                except Exception as e:
                    self.show_toast(f"Elevation profile: {e}")
        if len(points) < 2:
            w.show_waiting("Click the second point." if points else "Click the first point of the line on the map.", idx)
            return
        try:
            res = self._profile_fetch(lyr, points, units)
        except Exception as e:
            self.show_toast(f"Elevation profile: {e}")
            return
        w.unit_key[idx] = units
        w.show_result(res, self._measure_done, idx)
        if self._measure_done:
            canvas.set_measure_label(f"Profile {idx + 1} \u00b7 {res['total_distance']:,.2f} {res['distance_units']}")
        self.set_status(f"Elevation profile \u00b7 {lyr.name} \u00b7 {res['total_distance']:,.3f} {res['distance_units']}")

    # ---- Distance and Area: the cards of the earlier results ----
    def _wire_history(self, w) -> None:
        w.history.keepChanged.connect(lambda keep: setattr(self.map.canvas, "keep_measure", keep))
        w.history.removeRequested.connect(self._measure_card_removed)
        w.history.clearRequested.connect(self._measure_clear_all)

    def _measure_window_now(self):
        kind = getattr(self, "_measure_kind", "line")
        return {"line": getattr(self, "_measure_window", None), "polygon": getattr(self, "_area_window", None)}.get(kind)

    @staticmethod
    def _measure_entry_text(kind: str, res: dict) -> tuple[str, str]:
        """Headline and small line for a result card."""
        if kind == "polygon":
            d = AreaWindow.DECIMALS.get(res["unit"], 2)
            pd = 3 if res["perimeter_unit"] == "km" else 1
            return f"{res['area']:,.{d}f} {res['unit']}", f"Perimeter {res['perimeter']:,.{pd}f} {res['perimeter_unit']}"
        unit = res["unit"]
        d = 3 if unit in ("km", "mi") else 2
        n = len(res.get("segments", []))
        el = res.get("elevation")
        sub = f"{n} segment{'s' if n != 1 else ''}"
        if el:
            eu = res.get("elevation_unit", unit)
            sub += f" \u00b7 height change {el['difference']:+,.{3 if eu in ('km', 'mi') else 1}f} {eu}"
        return f"{res['total']:,.{d}f} {unit}", sub

    def _measure_fetch(self, kind: str, lyr, pts: list, units: str) -> dict:
        pixels = self._canvas_to_pixels(lyr, pts)
        if kind == "polygon":
            return self.api_post("/analysis/measure/area", {"layer_id": lyr.id, "pixels": pixels, "units": units,
                                                            "include_surface": False})
        return self.api_post("/analysis/measure/distance", {"layer_id": lyr.id, "pixels": pixels, "units": units,
                                                            "include_elevation": True})

    def _measure_record(self, kind: str, res: dict, w) -> None:
        """The line or area was just finished: add its card and write its result on the map."""
        canvas = self.map.canvas
        if not canvas.keep_measure or not canvas.measure_shapes:
            return
        shape = canvas.measure_shapes[-1]
        title, sub = self._measure_entry_text(kind, res)
        w.history.set_entry(shape["id"], title, sub, shape.get("color", "#e07b00"))
        w.history.unit_key[shape["id"]] = w.units.currentData()
        canvas.set_shape_label(shape["id"], f"{shape['id']} \u00b7 {title}")
        w.adjustSize()

    def _measure_refresh_cards(self, kind: str, lyr, w) -> None:
        """The units were changed: the earlier results are measured again in the new units."""
        canvas = self.map.canvas
        units = w.units.currentData()
        for i, shape in enumerate(canvas.measure_shapes):
            current = self._measure_done and i == len(canvas.measure_shapes) - 1
            if current or w.history.unit_key.get(shape["id"]) == units:
                continue
            try:
                res = self._measure_fetch(kind, lyr, shape["pts"], units)
            except Exception as e:
                self.show_toast(f"Measure: {e}")
                return
            title, sub = self._measure_entry_text(kind, res)
            w.history.set_entry(shape["id"], title, sub, shape.get("color", "#e07b00"))
            w.history.unit_key[shape["id"]] = units
            canvas.set_shape_label(shape["id"], f"{shape['id']} \u00b7 {title}")

    def _measure_card_removed(self, sid: int) -> None:
        w = self._measure_window_now()
        self.map.canvas.remove_measure_shape(sid)
        if w is not None:
            w.history.remove(sid)
            w.adjustSize()

    def _measure_clear_all(self) -> None:
        w = self._measure_window_now()
        self.map.canvas.clear_measure_shapes()
        if w is not None:
            w.history.clear()
            w.adjustSize()

    def _measure_shape_removed(self, sid: int) -> None:
        """A finished line was opened again (right-click): its card goes until it is finished again."""
        w = self._measure_window_now()
        if w is not None:
            w.history.remove(sid)
            w.adjustSize()

    def _profile_selected(self, idx: int) -> None:
        """A profile's numbers are shown: draw its line on the map thicker."""
        self.map.canvas.selected_shape_pos = idx
        self.map.canvas.update()

    def _profile_shape_clicked(self, pos: int) -> None:
        """Ctrl+click on a profile line on the map: show that profile's numbers."""
        w = getattr(self, "_profile_window", None)
        if w is not None and getattr(self, "_measure_kind", "") == "profile":
            w.select(pos)

    def _measure_cards_cleared(self) -> None:
        w = self._measure_window_now()
        if w is not None:
            w.history.clear()
            w.adjustSize()

    def _measure_changed(self, points: list, finished: bool) -> None:
        """A point was added or removed (or the line finished): measure again and update the box."""
        self._measure_points, self._measure_done = points, finished
        self._measure_update()

    def _measure_update(self) -> None:
        kind = getattr(self, "_measure_kind", "line")
        if kind == "polygon":
            self._area_update()
            return
        if kind == "profile":
            self._profile_update()
            return
        w = getattr(self, "_measure_window", None)
        lyr = getattr(self, "_measure_layer", None)
        points = getattr(self, "_measure_points", [])
        if w is None or lyr is None:
            return
        self._measure_refresh_cards("line", lyr, w)
        if len(points) < 2:
            w.show_waiting("Click the second point." if points else "Click the first point on the map.")
            return
        pixels = self._canvas_to_pixels(lyr, points)
        try:
            res = self.api_post("/analysis/measure/distance", {
                "layer_id": lyr.id, "pixels": pixels, "units": w.units.currentData(),
                "include_elevation": True})
        except Exception as e:
            self.show_toast(f"Distance: {e}")
            return
        w.show_result(res, self._measure_done, True)
        if self._measure_done:
            self._measure_record("line", res, w)
        self.set_status(f"Distance \u00b7 {lyr.name} \u00b7 {res['total']:,.3f} {res['unit']}")

    def _measure_closed(self) -> None:
        """The Measure box was closed: leave measuring and clear the line."""
        self._measure_points = []
        if self.map.canvas.mode == "measure":
            self.map.canvas.set_mode("explore")
        self.map.canvas.update()




    def run_terrain_derivative(self, tool: dict, values: dict) -> None:
        source_name = values.get("input_dem")
        source = next(
            (layer for layer in self.ws.rasters() if layer.name == source_name),
            None,
        )
        if source is None:
            raise ValueError("Load a raster DEM before running this analysis.")

        payload = {"layer_id": source.id}
        tool_id = tool["id"]
        routes = {
            "an-hillshade": ("/analysis/surface-analysis/hillshade", "hillshade"),
            "an-slope": ("/analysis/surface-analysis/slope", "slope"),
            "an-aspect": ("/analysis/surface-analysis/aspect", "aspect"),
            "an-curvature": ("/analysis/surface-analysis/curvature", "curvature"),
            "an-contours": ("/analysis/terrain-derivatives/contours", "contours"),
        }
        try:
            route, operation = routes[tool_id]
        except KeyError as exc:
            raise ValueError(f"Unsupported terrain analysis: {tool_id}") from exc

        if operation == "hillshade":
            payload.update({
                "azimuth": values["azimuth"],
                "altitude": values["altitude"],
                "z_factor": values["z_factor"],
            })
        elif operation == "slope":
            units = values["output_units"]
            payload["units"] = "percent" if units == "Percent rise" else "degrees"
            payload["method"] = "geodesic" if values.get("method") == "Geodesic" else "planar"
        elif operation == "aspect":
            payload["flat_as_minus_one"] = values["flat_areas_as_-1"]
            payload["method"] = "geodesic" if values.get("method") == "Geodesic" else "planar"
        elif operation == "contours":
            payload.update({
                "interval": values["interval"],
                "base": values["base_elevation"],
            })

        result = self.api_post(route, payload)
        info = result.get("layer")
        if not isinstance(info, dict):
            raise RuntimeError("Backend did not return a derived layer.")
        layer_id = info.get("id")
        layer_name = info.get("name")
        if not isinstance(layer_id, str) or not layer_id:
            raise RuntimeError("Backend returned a derived layer without an id.")
        if not isinstance(layer_name, str) or not layer_name:
            raise RuntimeError("Backend returned a derived layer without a name.")

        if operation == "contours":
            geojson = self.api_get(f"/file/add-data/layers/{layer_id}/geojson")
            layer = self.ws.add_contour_layer(layer_id, layer_name, geojson, source)
        else:
            ramp = {
                "hillshade": "greys",
                "slope": "slope",
                "aspect": "viridis",
                "curvature": "diverging",
            }[operation]
            rgba = self._decode_raster_image(
                self.api_get_bytes(f"/file/export/map-image/{layer_id}?ramp={ramp}")
            )
            stats_result = self.api_get(f"/file/export/statistics/{layer_id}")
            histogram_result = self.api_get(
                f"/analysis/quality-statistics/histogram/{layer_id}",
                {"bins": 30},
            )
            stats = {
                "min": stats_result["min"],
                "max": stats_result["max"],
                "mean": stats_result["mean"],
                "std": stats_result["std_dev"],
                "median": stats_result["median"],
                "count": stats_result["count"],
                "nodata_count": stats_result["nodata_count"],
                "hist": np.asarray(histogram_result["counts"]),
                "edges": np.asarray(histogram_result["bin_edges"]),
            }
            layer = self.ws.add_raster_image(
                layer_id,
                layer_name,
                rgba,
                f"Derived from {source.name}",
                info,
                stats,
            )

        self.contents.rebuild()
        self.map.canvas.invalidate()
        self.on_layer_selected(layer.id)
        self.map.canvas.fit()
        feature_count = result.get("extra", {}).get("feature_count")
        if operation == "contours":
            self.show_toast(f"Contours created · {feature_count} levels")
        else:
            self.show_toast(f"{tool['label']} created · {layer.name}")

    # ----- toggles / panes --------------------------------------------------
    def is_on(self, key: str) -> bool:
        if key.startswith("layer:"):
            try:
                return self.ws.layer(key[6:]).visible
            except KeyError:
                return False
        return self.flags.get(key, False)

        #..............changed the functionality to make it clickable for all the layers rather than adding a backend......................
    def is_available(self, key: str) -> bool:
        return True

    def toggle(self, key: str) -> None:
        if key.startswith("layer:"):
            lid = key[6:]
            try:
                on = not self.ws.layer(lid).visible
            except KeyError:
                self.show_toast("No layer loaded yet · connect data to enable this")
                return
            self.set_layer_visible(lid, on)
            self.contents.set_visible(lid, on)
        else:
            self.set_flag(key, not self.flags[key])

    def set_flag(self, key: str, on: bool) -> None:
        self.flags[key] = on
        if key in ("contents", "statistics"):
            pane = self.contents if key == "contents" else self.inspector
            was_hidden = pane.isHidden()
            if not on and not was_hidden:
                sizes = self.splitter.sizes()
                if all(sizes):
                    self._saved_sizes = sizes
            pane.setVisible(on)
            if on and was_hidden:
                self.splitter.setSizes(self._saved_sizes if all(self._saved_sizes) else [290, 900, 330])
            if key == "statistics" and on and self.inspector.stack.currentWidget() is self.inspector.tool_scroll:
                if self.selected and self.ws.has_layer(self.selected):
                    self.inspector.show_layer(self.ws.layer(self.selected))
                else:
                    self.inspector.show_empty_state()
            self.map.set_pane_buttons(self.flags["contents"], self.flags["statistics"])
        else:
            self.map.set_element_visible(key, on)
        self.ribbon.refresh_checks()

    def set_layer_visible(self, lid: str, on: bool) -> None:
        if on and not self.ws.in_canvas(lid):             # ticking a loaded layer adds it to this canvas
            self.ws.add_layer_to_canvas(lid, self.ws.active_canvas)
            QTimer.singleShot(0, self.contents.rebuild)      # after this click is fully handled
        self.ws.layer(lid).visible = on
        self.mark_dirty()
        self.map.canvas.update()
        self.ribbon.refresh_checks()
        self.map.refresh_pixel()

    def _layers_reordered(self) -> None:
        self.mark_dirty()
        self.map.canvas.invalidate()
        QTimer.singleShot(60, self.contents.rebuild)          # after the drag has fully ended
        self.set_status("Layer order changed")

    def _rename_layer(self, lid: str, name: str) -> None:
        self.ws.layer(lid).name = name
        self.mark_dirty()
        self.contents.rebuild()
        if self.selected == lid:
            self.inspector.show_layer(self.ws.layer(lid))
        self.set_status(f"Renamed to {name}")

    def _remove_layer(self, lid: str) -> None:
        try:
            lyr = self.ws.layer(lid)
        except KeyError:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Remove layer")
        box.setText(f"Remove \u201c{lyr.name}\u201d from the project?")
        box.setInformativeText("It disappears from every map canvas. This cannot be undone.")
        remove = box.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not remove:
            return
        warning = ""
        if lyr.user_added:                                    # layers of the sample workspace have no backend copy
            try:
                httpx.delete(f"{BASE_URL}{API_PREFIX}/file/add-data/layers/{lid}", timeout=10).raise_for_status()
            except Exception as exc:
                warning = f" (the backend could not delete it: {_friendly_error(exc)})"
        self.ws.remove_layer(lid)
        if self.selected == lid:
            self.selected = None
            self.on_layer_selected(None)
        self.contents.rebuild()
        self.map.canvas.invalidate()
        self.ribbon.refresh_checks()
        self.map.refresh_pixel()
        self.mark_dirty()
        self.show_toast(f"Removed {lyr.name}{warning}")

    def _menu_opacity_changed(self, lid: str, value: int) -> None:
        """Opacity slider in a layer's right-click menu: update the map now and keep the side panel in step."""
        self._opacity_changed(lid, value)
        if self.selected == lid:
            QTimer.singleShot(0, lambda: self.inspector.show_layer(self.ws.layer(lid)))

    def _opacity_changed(self, lid: str, value: int) -> None:
        self.ws.layer(lid).opacity = value
        self.mark_dirty()
        self.map.canvas.update()

    # ----- layers -----------------------------------------------------------
    def on_layer_selected(self, lid: str | None) -> None:
        if lid is None:
            self.selected = None
            self.contents.select("")
            self.map.set_selected_layer(None)
            self.inspector.show_empty_state()
            return

        self.selected = lid
        lyr = self.ws.layer(lid)
        if lyr.group == "raster" and lyr.user_added and not lyr.visible:
            self.set_layer_visible(lid, True)
            self.contents.set_visible(lid, True)
            self.map.canvas.zoom_to_layer(lid)
        self.contents.select(lid)
        self.map.set_selected_layer(lid)
        self.inspector.show_layer(lyr)

    def _show_stats_for(self, lid: str | None) -> None:
        if not lid or not any(l.id == lid for l in self.ws.layers):
            self.set_flag("statistics", True)
            self.inspector._show_empty_state()
            return
        self.set_flag("statistics", True)
        self.inspector.show_layer(self.ws.layer(lid))

    def _regions_changed(self) -> None:
        self.mark_dirty()
        n = len(self.ws.regions)
        self.contents.set_sub("regions", f"{n} polygon{'s' if n != 1 else ''}")
        if self.selected == "regions":
            self.inspector.show_layer(self.ws.layer("regions"))

    def _mode_changed(self, mode: str) -> None:
        for name in ("_measure_window", "_area_window", "_profile_window"):
            w = getattr(self, name, None)
            if mode != "measure" and w is not None and w.isVisible():
                w.hide()

    # ----- actions (referenced by tool["action"]) ---------------------------
    def act_mode_explore(self) -> None:
        self.map.canvas.set_mode("explore")

    def act_mode_select(self) -> None:
        self.map.canvas.set_mode("select")

    def act_draw_region(self) -> None:
        self.ws.layer("regions").visible = True
        self.contents.set_visible("regions", True)
        self.map.canvas.set_mode("draw")
        self.map.canvas.setFocus()

    def act_delete_region(self) -> None:
        if not self.map.canvas.delete_selected():
            self.show_toast("Select a region first (Select Region tool)")

    def act_clear_regions(self) -> None:
        self.map.canvas.clear_regions()
        self.show_toast("All editing regions removed")

    def act_zoom_in(self) -> None:
        """Zoom In tool: drag a box around an area to zoom to it (or click to zoom in)."""
        self.map.canvas.set_mode("zoom_in")
        self.map.canvas.setFocus()

    def act_zoom_out(self) -> None:
        """Zoom Out tool: drag a box or click to zoom out."""
        self.map.canvas.set_mode("zoom_out")
        self.map.canvas.setFocus()

    def act_swipe(self) -> None:
        """Swipe: drag a vertical line to compare the top raster with the layers below it."""
        canvas = self.map.canvas
        if canvas.mode == "swipe":
            canvas.set_mode("explore")
            return
        shown = [l for l in self.ws.rasters() if l.visible and l.rgba is not None]
        if len(shown) < 2:
            self.show_toast("Swipe compares the top raster with the one below it. Show two rasters first.")
            return
        canvas.set_mode("swipe")
        canvas.setFocus()

    def act_full_extent(self) -> None:
        self.map.canvas.fit()

    def act_zoom_selected(self) -> None:
        if not self.selected:
            self.show_toast("Select a layer first")
            return
        self.map.canvas.zoom_to_layer(self.selected)

    def act_attribute_table(self) -> None:
        """View > Attribute Table: the rows of the selected vector layer (or the first one loaded)."""
        chosen = next((l for l in self.ws.layers if l.id == self.selected and l.shapes), None)
        chosen = chosen or next((l for l in self.ws.layers if l.shapes), None)
        if chosen is None:
            self.show_toast("Load a vector layer (Add Vector) to see its attribute table.")
            return
        self._open_attribute_table(chosen.id)

    def _open_attribute_table(self, lid: str) -> None:
        """Open the attribute table window for one vector layer (also used by the layer's ... menu)."""
        chosen = next((l for l in self.ws.layers if l.id == lid and l.shapes), None)
        if chosen is None:
            return
        if getattr(self, "_attribute_window", None) is None:
            self._attribute_window = AttributeTableWindow(self, self.api_get)
        w = self._attribute_window
        try:
            w.show_layer(chosen.id, chosen.name)
        except RuntimeError as e:
            self.show_toast(str(e))
            return
        if not w.isVisible():
            w.move(self.map.mapToGlobal(QPoint(40, 90)))
        w.show()
        w.raise_()

    def act_show_stats(self) -> None:
        self._show_stats_for(self.selected)

    def act_toggle_stats(self) -> None:
        """Ribbon button: first click opens the statistics panel, the next click closes it."""
        showing_stats = (self.flags.get("statistics", False) and not self.inspector.isHidden()
                         and self.inspector.stack.currentWidget() is not self.inspector.tool_scroll)
        if showing_stats:
            self.set_flag("statistics", False)
        else:
            self._show_stats_for(self.selected)

    def act_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def act_exit_app(self) -> None:
        self.close()

    def act_preview_edit(self) -> None:
        if not self.ws.regions:
            self.show_toast("Draw at least one editing region first")
            return
        self.map.canvas.set_preview("edit")
        self.map.show_preview("Modification preview")

    def act_preview_mosaic(self) -> None:
        for lid in ("dem", "east"):
            self.set_layer_visible(lid, True)
            self.contents.set_visible(lid, True)
        self.map.canvas.fit()
        self.map.canvas.set_preview("mosaic")
        self.map.show_preview("Mosaic preview")

    def act_discard_preview(self) -> None:
        self.map.canvas.set_preview(None)
        self.map.show_preview(None)
        self.show_toast("Preview discarded")

    def _restore_canvases(self, res: dict) -> None:
        """Opened project: bring back its map canvases (an old project arrives as one canvas)."""
        saved = res.get("canvases") or []
        if not saved:
            return
        self.ws.load_canvases(saved, res.get("active_canvas"))
        self.map.set_canvases([{"id": c["id"], "name": c["name"], "view": c.get("view")} for c in saved],
                              self.ws.active_canvas)

    def _canvas_switched(self, cid: str) -> None:
        """Another map canvas tab was chosen: show its own layers and regions."""
        self.ws.switch_canvas(cid)
        self.map.canvas.set_preview(None)
        self.map.show_preview(None)
        self.map.canvas.set_mode("explore")
        self.map.canvas.invalidate()
        self.contents.rebuild()
        self.map.update_annotation()
        self.on_layer_selected(self.ws.layers[0].id if self.ws.layers else None)
        self.ribbon.refresh_checks()

    def _layer_dropped(self, lid: str, cid: str) -> None:
        """A layer was dragged onto a canvas tab: that canvas shows it too (the data is shared)."""
        name = self.ws.canvas_entry(cid)["name"]
        if not self.ws.add_layer_to_canvas(lid, cid):
            self.set_status(f"That layer is already in {name}")
            return
        if cid == self.ws.active_canvas:
            self.contents.rebuild()
            self.map.canvas.invalidate()
        self.set_status(f"Layer added to {name}")

    def _refresh_everything(self) -> None:
        self.map.canvas.invalidate()
        self.contents.rebuild()
        self.map.update_annotation()
        self.map.canvas.set_preview(None)
        self.map.show_preview(None)
        self.map.canvas.set_mode("explore")
        self.on_layer_selected(self.ws.layers[0].id if self.ws.layers else None)
        self.ribbon.refresh_checks()
        self.map.canvas.fit()

    def act_reset_workspace(self) -> None:
        self.ws.reset()
        self.map.reset_canvases()
        self._refresh_everything()
        self.show_toast("Sample workspace restored")

    # ----- project: the backend holds the layers and writes the project file ------
    def _init_project_actions(self) -> None:
        self._dirty = False
        self._project_ready = True
        self._last_dir = str(Path.home())
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.act_new_project)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.act_save_project_as)
        self._refresh_title()

    def _autosave_tick(self) -> None:
        """Every minute: save the project when Auto-save is on, the project has a file and has unsaved changes."""
        invalidate_project_defaults()
        try:
            minutes = int(_project_defaults().get("auto_save_minutes", 0))
        except Exception:
            return
        if not minutes or not self._dirty or self.project_path is None:
            self._autosave_ticks = 0
            return
        self._autosave_ticks += 1
        if self._autosave_ticks >= minutes:
            self._autosave_ticks = 0
            if self._save_to(self.project_path, self.project_name, "/file/project/save"):
                self.show_toast("Project auto-saved")

    def mark_dirty(self) -> None:
        if getattr(self, "_project_ready", False) and not self._dirty:
            self._dirty = True
            self._refresh_title()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._refresh_title()

    def _refresh_title(self) -> None:
        self.setWindowTitle(f"{self.project_name}{'*' if self._dirty else ''} - {APP_NAME}")
        self.map.set_project_name(self.project_name)
        self.map.tab_dot.setVisible(self._dirty)

    def _confirm_discard(self, action: str) -> bool:
        """True = go ahead. With unsaved changes: Save / Don't save / Cancel."""
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved changes")
        box.setText(f"Save changes to “{self.project_name}” before you {action}?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Don't Save", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        if box.clickedButton() is cancel:
            return False
        return self.act_save_project() if box.clickedButton() is save else True

    def closeEvent(self, event) -> None:            # window X / Alt+F4 / File > Exit
        event.accept() if self._confirm_discard("close") else event.ignore()

    def act_new_project(self) -> None:
        if not self._confirm_discard("create a new project"):
            return
        try:
            self.api_post("/file/project/new", {"name": "Untitled project"})
        except Exception as exc:
            self.show_toast(f"New project failed: {_message(exc)}")
            return
        self.ws.reset()
        self.map.reset_canvases()
        self.project_path = None
        self.project_name = PROJECT_TITLE
        self._refresh_everything()
        self._mark_clean()
        self.show_toast("New project")

    def act_name_project(self) -> None:
        dialog = ProjectNameDialog(self.project_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.project_name = dialog.project_name
        self._refresh_title()
        self.mark_dirty()

    def _gui_state(self) -> dict:
        """What only the window knows; the backend stores it untouched inside the project."""
        c = self.map.canvas
        return {
            "ramp": self.ws.ramp_name,
            "regions": [[list(p) for p in poly] for poly in self.ws.regions],
            "view": {"scale": c.scale, "ox": c.ox, "oy": c.oy},
            "layers": {l.id: {"visible": l.visible, "opacity": l.opacity} for l in self.ws.layers},
            "order": [l.id for l in self.ws.layers],
            "names": {l.id: l.name for l in self.ws.all_layers()},
        }

    def _canvases_state(self) -> dict:
        """The map canvases (own layers, view and regions each), stored by the backend in the project."""
        views = self.map.canvas_views()
        canvases = self.ws.canvases_for_save()
        for c in canvases:
            c["view"] = views.get(c["id"])
        return {"canvases": canvases, "active_canvas": self.ws.active_canvas}

    def act_save_project(self) -> bool:
        """Save over the current file (asks for a name the first time). True = saved."""
        if self.project_path is None:
            return self.act_save_project_as()
        return self._save_to(self.project_path, self.project_name, "/file/project/save")

    def act_save_project_as(self) -> bool:
        start = str(Path(self._last_dir) / f"{self.project_name}{PROJECT_EXT}")
        path, _ = QFileDialog.getSaveFileName(self, "Save project as", start, PROJECT_FILTER)
        if not path:
            return False
        p = Path(path)
        if p.suffix.lower() not in (PROJECT_EXT, ".agtaam", ".json"):
            p = p.with_suffix(PROJECT_EXT)
        return self._save_to(p, p.stem, "/file/project/save-as")

    def act_project_settings(self) -> None:
        """File > Project > Project Settings: Analyze in UTM, UTM zone, resampling (saved in the project)."""
        try:
            current = self.api_get("/file/project/settings")
        except Exception as exc:
            self.show_toast(f"Project settings: {_message(exc)}")
            return
        layer = next(iter(self.ws.rasters()), None)

        def preview(zone: str):
            if layer is None:
                return None
            return self.api_get("/file/project/settings/utm-preview", {"layer_id": layer.id, "zone": zone})

        dlg = ProjectSettingsDialog(self, current, layer.name if layer else None, preview)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new = dlg.values()
        if new == current:
            return
        try:
            self.api_put("/file/project/settings", new)
        except Exception as exc:
            QMessageBox.warning(self, "Project Settings", f"Could not save the settings:\n{_message(exc)}")
            return
        invalidate_project_defaults()
        if new.get("scale_bar") != current.get("scale_bar"):
            self.set_flag("scale_bar", bool(new["scale_bar"]))      # same switch as View > Scale Bar
        self.mark_dirty()
        self.map.refresh_pixel()                                    # coordinate format shows right away
        if self.selected:                                  # decimals and height unit show right away
            try:
                self.inspector.show_layer(self.ws.layer(self.selected))
            except Exception:
                pass
        self.show_toast("Analyze in UTM is ON" if new["analyze_in_utm"] else "Project settings saved")

    def _save_to(self, path: Path, name: str, route: str) -> bool:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.api_post(route, {"path": str(path), "name": name, "gui": self._gui_state(),
                                        **self._canvases_state()})
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Save project", f"Could not save the project:\n{_message(exc)}")
            return False
        QApplication.restoreOverrideCursor()
        self.project_path = Path(res.get("path") or path)
        self._last_dir = str(self.project_path.parent)
        self.project_name = res.get("name", name)
        self._mark_clean()
        skipped = res.get("skipped_layers") or []
        if skipped:
            QMessageBox.warning(self, "Save project",
                                "These layers could not be written and are not in the project:\n\n"
                                + "\n".join(f"  • {n}" for n in skipped))
        self.show_toast(f"Project saved · {self.project_path.name}")
        return True

    def act_open_project(self) -> None:
        if not self._confirm_discard("open another project"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", self._last_dir, PROJECT_FILTER)
        if not path:
            return
        path = Path(path)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.api_post("/file/project/open", {"path": str(path)})
            problems = self._redraw_layers(res.get("layers") or [], res.get("gui") or {})
            self._restore_canvases(res)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Open project", f"Could not open the project:\n{_message(exc)}")
            return
        QApplication.restoreOverrideCursor()
        self.project_path = path
        self._last_dir = str(path.parent)
        self.project_name = res.get("name", path.stem)
        self._refresh_everything()
        self.map.restore_current_view()
        v = (res.get("gui") or {}).get("view")
        if v:
            c = self.map.canvas
            c.scale, c.ox, c.oy = v["scale"], v["ox"], v["oy"]
            c.update()
            c.viewChanged.emit()
        self._regions_changed()
        self._mark_clean()
        lines = [f"  • {n}  (file not found)" for n in res.get("missing_layers") or []]
        lines += [f"  • {n}" for n in problems]
        if lines:
            QMessageBox.warning(self, "Open project",
                                "The project opened, but some layers could not be loaded:\n\n" + "\n".join(lines))
        self.show_toast(f"Project opened · {path.name}")

    def _redraw_layers(self, layers: list, gui: dict) -> list[str]:
        """Draw the layers the backend sent. Returns notes about layers that cannot be drawn."""
        notes: list[str] = []
        self.ws.reset()
        self.map.reset_canvases()
        if gui.get("ramp"):
            self.ws.ramp_name = gui["ramp"]
        bottom_first = list(reversed(layers))                  # the backend lists the top layer first
        for kind in ("raster", "vector"):
            for info in (i for i in bottom_first if i["kind"] == kind):
                try:
                    self._draw_one(info)
                except Exception as exc:
                    notes.append(f"{info['name']}: {_message(exc)}")
        notes += [f"{i['name']}: basemap layers cannot be drawn in this window yet"
                  for i in layers if i["kind"] == "basemap"]
        saved = gui.get("layers", {})
        for lyr in self.ws.layers:                             # visibility, opacity, order the user had
            s = saved.get(lyr.id)
            if s:
                lyr.visible, lyr.opacity = bool(s.get("visible", True)), int(s.get("opacity", 100))
        names = gui.get("names", {})
        for lyr in self.ws.all_layers():                       # names the user typed in the Layers panel
            if names.get(lyr.id):
                lyr.name = names[lyr.id]
        order = {lid: n for n, lid in enumerate(gui.get("order", []))}
        if order:
            self.ws.layers.sort(key=lambda l: order.get(l.id, len(order)))
        self.ws.regions = [[tuple(p) for p in poly] for poly in gui.get("regions", [])]
        return notes

    def _draw_one(self, info: dict) -> None:
        lid = info["id"]
        if info["kind"] == "raster":                           # same steps as Add Raster
            d = info["display"]
            rgba = self._decode_raster_image(self.api_get_bytes(f"/file/export/map-image/{lid}?ramp={d['ramp']}"))
            s, h = d["statistics"], d["histogram"]
            stats = {"min": s["min"], "max": s["max"], "mean": s["mean"], "std": s["std_dev"],
                     "median": s["median"], "count": s["count"], "nodata_count": s["nodata_count"],
                     "hist": np.asarray(h["counts"]), "edges": np.asarray(h["bin_edges"])}
            parent = info.get("derived_from")
            desc = (f"Derived from {self.ws.layer(parent).name}"
                    if info.get("tool") and parent and self.ws.has_layer(parent) else info.get("source") or "")
            self.ws.add_raster_image(lid, info["name"], rgba, desc, info, stats)
        elif info.get("tool") == "contours" and info.get("derived_from") and self.ws.has_layer(info["derived_from"]):
            geo = self.api_get(f"/file/add-data/layers/{lid}/geojson")
            self.ws.add_contour_layer(lid, info["name"], geo, self.ws.layer(info["derived_from"]))
        elif info.get("tool") is None:
            self._show_vector(info)
        else:
            raise ValueError("this kind of vector layer cannot be drawn in this window yet")

    # ----- vector layers: the backend sends shapes already in drawing cells --------
    def _vector_shapes(self, layer_id: str) -> tuple[dict, str | None]:
        """Shapes lined up with the first raster on the map (or fitted into the window)."""
        r = next((l for l in self.ws.rasters() if l.bounds and l.rgba is not None), None)
        if r is None:
            return self.api_get(f"/file/add-data/layers/{layer_id}/shapes",
                                {"fit_width": self.ws.WIDTH, "fit_height": self.ws.HEIGHT}), None
        h, w = r.rgba.shape[:2]
        return self.api_get(f"/file/add-data/layers/{layer_id}/shapes",
                            {"raster": r.id, "width": w, "height": h}), r.id

    def _show_vector(self, info: dict) -> Layer:
        shapes, raster_id = self._vector_shapes(info["id"])
        meta = info.get("meta") or {}
        layer = Layer(id=info["id"], name=info.get("name", "vector"),
                      sub=f"{shapes['total']} features · {meta.get('geometry', 'Vector')}",
                      group="vector", kind="vector", visible=True, desc=info.get("source") or "",
                      user_added=True, shapes=shapes, vec_raster=raster_id,
                      vec_color=VECTOR_COLORS[sum(1 for l in self.ws.layers if l.shapes) % len(VECTOR_COLORS)])
        layer.vec_info = info
        top = next((i for i, l in enumerate(self.ws.layers) if l.group == "vector"), len(self.ws.layers))
        self.ws.layers.insert(top, layer)                      # a new layer goes on top, like ArcMap
        return layer

    def _refit_vectors(self) -> None:
        """A raster was just added: line up vector files that were drawn on their own."""
        for lyr in self.ws.layers:
            if lyr.shapes and lyr.vec_raster is None:
                try:
                    lyr.shapes, lyr.vec_raster = self._vector_shapes(lyr.id)
                except Exception:
                    pass                                       # keep the stand-alone drawing

    # --- add data ------------------------------------------------------------
    def _add_vector_flow(self, path: str) -> None:
        """Add a vector file or geodatabase. A file with several layers asks which ones to add."""
        stem = Path(path).stem
        try:
            names = self.api_get("/file/add-data/vector-layers", {"path": path}).get("layers", [])
        except Exception as exc:
            self.show_toast(f"Add vector failed: {_message(exc)}")
            return
        if len(names) > 1:
            dlg = VectorLayerChooser(self, Path(path).name, names)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            picks = dlg.chosen()
            if not picks:
                self.show_toast("No layer ticked")
                return
        else:
            picks = names or [None]
        added, problems = [], []
        for pick in picks:
            payload = {"path": path, "name": pick or stem}
            if pick:
                payload["layer"] = pick
            try:
                info = self.api_post("/file/add-data/vector", payload)
                try:
                    layer = self._show_vector(info)
                except Exception:
                    try:
                        httpx.delete(f"{BASE_URL}{API_PREFIX}/file/add-data/layers/{info['id']}", timeout=10)
                    except Exception:
                        pass
                    raise
                added.append(layer)
            except Exception as exc:
                traceback.print_exc()
                problems.append(f"{pick or stem}: {_message(exc)}")
        if added:
            self.contents.rebuild()
            self.map.canvas.invalidate()
            self.on_layer_selected(added[-1].id)
            if not any(l.group == "raster" for l in self.ws.layers):
                self.map.canvas.fit()
            self.mark_dirty()
        if problems:
            QMessageBox.warning(self, "Add vector", "Some layers could not be added:\n\n" + "\n".join(problems))
        if added:
            self.show_toast(f"Vector added successfully: {added[0].name}" if len(added) == 1
                            else f"{len(added)} vector layers added")

    def _add_data(
        self,
        title: str,
        file_filter: str,
        kind: str
    ) -> None:

    # 1. Open file selection dialog
        file_path, _ = QFileDialog.getOpenFileName(
        self,
        title,
        "",
        file_filter
    )

    # User cancelled file selection
        if not file_path:
            return

        if kind == "vector":
            self._add_vector_flow(file_path)
            return

        try:
        # 2. Extract filename without extension
            file_name = Path(file_path).stem

        # 3. Prepare API payload
            payload = {
            "path": file_path,
            "name": file_name
        }

        # 4. Call FastAPI endpoint
            if kind == "raster":
                info = self.api_post(
                "/file/add-data/raster",
                payload
            )
            elif kind == "vector":
                info = self.api_post("/file/add-data/vector", payload)
            else:
                raise ValueError(
                f"Unsupported data type: {kind}"
            )

            if kind == "vector":
                try:
                    layer = self._show_vector(info)
                except Exception:
                    try:
                        httpx.delete(f"{BASE_URL}{API_PREFIX}/file/add-data/layers/{info['id']}", timeout=10)
                    except Exception:
                        pass
                    raise
                self.contents.rebuild()
                self.map.canvas.invalidate()
                self.on_layer_selected(layer.id)
                if not any(l.group == "raster" for l in self.ws.layers):
                    self.map.canvas.fit()
                self.mark_dirty()
                self.show_toast(f"Vector added successfully: {file_name}")
                return

            if kind == "raster":
                layer_id = info.get("id")
                if not isinstance(layer_id, str) or not layer_id:
                    raise RuntimeError("Backend did not return a raster layer id.")
                png = self.api_get_bytes(f"/file/export/map-image/{layer_id}")
                rgba = self._decode_raster_image(png)
                stats_result = self.api_get(f"/file/export/statistics/{layer_id}")
                histogram_result = self.api_get(
                    f"/analysis/quality-statistics/histogram/{layer_id}",
                    {"bins": 30},
                )
                stats = {
                    "min": stats_result["min"],
                    "max": stats_result["max"],
                    "mean": stats_result["mean"],
                    "std": stats_result["std_dev"],
                    "median": stats_result["median"],
                    "count": stats_result["count"],
                    "nodata_count": stats_result["nodata_count"],
                    "hist": np.asarray(histogram_result["counts"]),
                    "edges": np.asarray(histogram_result["bin_edges"]),
                }
                layer = self.ws.add_raster_image(
                    layer_id,
                    info.get("name", file_name),
                    rgba,
                    file_path,
                    info,
                    stats,
                )
                self._refit_vectors()
                self.contents.rebuild()
                self.map.canvas.invalidate()
                self.on_layer_selected(layer.id)
                self.map.canvas.fit()
                self.mark_dirty()

            self.show_toast(f"Raster added successfully: {file_name}")

        except Exception as e:
            traceback.print_exc()
            self.show_toast(f"Add {kind} failed: {_message(e)}")

    def act_add_raster(self) -> None:
        self._add_data("Add raster", "Raster (*.tif *.tiff *.img *.asc);;All files (*)", "raster")

    def act_add_vector(self) -> None:
        """Add Vector: a menu offers a vector file or a file geodatabase (.gdb is a folder)."""
        from PyQt6.QtGui import QCursor
        menu = QMenu(self)
        menu.addAction(icon("vector_add", "#244557", 18), "Vector file\u2026",
                       lambda: self._add_data("Add vector", VECTOR_FILTER, "vector"))
        menu.addAction(icon("database", "#244557", 18), "File geodatabase (.gdb)\u2026", self._add_geodatabase)
        menu.exec(QCursor.pos())

    def _add_geodatabase(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a file geodatabase (.gdb folder)")
        if not folder:
            return
        if not folder.lower().rstrip("/\\").endswith(".gdb"):
            self.show_toast("That folder is not a file geodatabase (its name should end in .gdb)")
            return
        self._add_vector_flow(folder)

    def act_add_basemap(self) -> None:
        self._add_data("Add basemap", "Basemap (*.tif *.tiff *.png *.jpg);;All files (*)", "basemap")

    # ----- File > Export -----------------------------------------------------------
    def _pick_layer(self, title: str, layers: list, what: str):
        """The layer to export: the only one, or one chosen from a list."""
        if not layers:
            self.show_toast(f"{title}: there is no {what} layer to export")
            return None
        if len(layers) == 1:
            return layers[0]
        names = [l.name for l in layers]
        name, ok = QInputDialog.getItem(self, title, f"Which {what} layer?", names, 0, False)
        return layers[names.index(name)] if ok else None

    def _export_with_backend(self, title: str, route: str, payload: dict) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.api_post(route, payload)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, title, f"Could not export:\n{_message(exc)}")
            return
        QApplication.restoreOverrideCursor()
        out = Path(str(result.get("path", "")))
        self._last_dir = str(out.parent)
        self.show_toast(f"Saved \u00b7 {out.name}")

    def act_export_raster(self) -> None:
        layer = self._pick_layer("Export Raster", self.ws.rasters(), "raster")
        if layer is None:
            return
        filters = {"GeoTIFF (*.tif *.tiff)": "geotiff", "ASCII Grid (*.asc)": "ascii", "XYZ points (*.csv)": "xyz"}
        start = str(Path(self._last_dir) / layer.name)
        path, chosen = QFileDialog.getSaveFileName(self, "Export raster", start, ";;".join(filters))
        if not path:
            return
        self._export_with_backend("Export Raster", "/file/export/elevations",
                                  {"layer_id": layer.id, "path": path, "format": filters.get(chosen, "geotiff")})

    def act_export_vector(self) -> None:
        vectors = [l for l in self.ws.layers if l.group == "vector"]
        layer = self._pick_layer("Export Vector", vectors, "vector")
        if layer is None:
            return
        filters = {"GeoJSON (*.geojson)": "geojson", "Shapefile (*.shp)": "shapefile",
                   "GeoPackage (*.gpkg)": "gpkg", "CSV, points only (*.csv)": "csv"}
        start = str(Path(self._last_dir) / layer.name)
        path, chosen = QFileDialog.getSaveFileName(self, "Export vector", start, ";;".join(filters))
        if not path:
            return
        self._export_with_backend("Export Vector", "/file/export/vector",
                                  {"layer_id": layer.id, "path": path, "format": filters.get(chosen, "geojson")})

    def act_export_image(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export map image", "terrain_map.png",
                                              "PNG image (*.png);;JPEG image (*.jpg *.jpeg)")
        if path:
            image = self.map.surface.grab()
            author = str(_project_defaults().get("author") or "").strip()       # Project Settings > Project
            if author:
                self._stamp_credit(image, f"{author}  \u00b7  {datetime.now():%d %b %Y}")
            ok = image.save(path)
            self.show_toast(f"Map image saved · {Path(path).name}" if ok else "Could not save the image")

    @staticmethod
    def _stamp_credit(image, text: str) -> None:
        """Small credit line in the bottom-right corner of an exported map image."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        box = painter.fontMetrics().boundingRect(text)
        w, h = box.width() + 20, box.height() + 10
        rect = QRectF(image.width() - w - 12, image.height() - h - 12, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 210))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#34404c"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
