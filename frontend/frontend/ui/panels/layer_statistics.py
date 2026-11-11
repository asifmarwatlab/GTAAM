from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np
from PyQt6.QtCore import QMimeData, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QLinearGradient, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui.panels.icon_generator import icon, pixmap

DASH = "—"

# ----------------------------------------------------------------------------
# colour ramps
# ----------------------------------------------------------------------------
RAMPS: dict[str, list[tuple[float, str]]] = {
    "Hypsometric": [
        (0.00, "#2f6f5e"), (0.20, "#6fa36b"), (0.40, "#c9c779"),
        (0.60, "#c79a5b"), (0.80, "#8a6445"), (1.00, "#f4f1ec"),
    ],
    "Greyscale": [(0.0, "#1b1f23"), (1.0, "#f5f7f8")],
    "Spectral": [
        (0.00, "#2b4c9b"), (0.25, "#3fa7c9"), (0.50, "#8fd08a"),
        (0.75, "#f0c24a"), (1.00, "#c8402a"),
    ],
}
SLOPE_RAMP = [(0.0, "#f2f6e9"), (0.35, "#e8d77a"), (0.7, "#e08a3c"), (1.0, "#b83a2e")]
NEUTRAL_RAMP = [(0.0, "#1b1f23"), (1.0, "#f5f7f8")]


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ramp_lut(stops: list[tuple[float, str]], n: int = 256) -> np.ndarray:
    pos = np.array([s[0] for s in stops])
    cols = np.array([_hex_rgb(s[1]) for s in stops], dtype=float)
    t = np.linspace(0, 1, n)
    return np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], axis=1).astype(np.uint8)


def fmt(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}"


# ----------------------------------------------------------------------------
# data model (no built-in sample data)
# ----------------------------------------------------------------------------
@dataclass
class Layer:
    id: str
    name: str
    sub: str
    group: str                       # raster | vector | basemap
    kind: str                        # swatch style: dem gray slope vector contours base
    visible: bool = False
    opacity: int = 100
    data: Optional[np.ndarray] = None
    col0: int = 0                    # column offset in the workspace grid
    unit: str = "m"
    value_label: str = "Elevation"
    desc: str = ""
    rgba: Optional[np.ndarray] = None
    vector_lines: list[tuple[float, np.ndarray]] = field(default_factory=list)
    user_added: bool = False
    _stats: Optional[dict] = field(default=None, repr=False)
    source_width: int | None = None
    source_height: int | None = None
    bounds: tuple[float, float, float, float] | None = None
    crs: str | None = None
    pixel_size: tuple[float, float] | None = None
    pixel_size_m: tuple[float, float] | None = None    # ground size of one cell in metres (from the backend)
    nodata: float | None = None
    shapes: Optional[dict] = None    # vector file: shapes in drawing cells (from the backend)
    vec_color: str = "#1f6f9a"
    vec_raster: Optional[str] = None  # raster the shapes were lined up with
    vec_info: Optional[dict] = None   # what the backend said about the layer


class SampleWorkspace:

    X0 = 0.0               
    Y_TOP = 0.0            
    CELL = 10.0
    EPSG = 32643
    CRS_NAME = "WGS 84 / UTM 43N"
    WIDTH, HEIGHT = 768, 512      
    Z_MIN, Z_MAX = 0.0, 1.0

    def __init__(self) -> None:
        self.ramp_name = "Hypsometric"
        self.layers: list[Layer] = []
        self.regions: list[list[tuple[float, float]]] = []
        self.contours: list[tuple[float, list[np.ndarray]]] = []
        self.reset()

    def reset(self) -> None:
        self.ramp_name = "Hypsometric"
        self.layers = []
        self.regions = []
        self.contours = []
        # map canvases: ws.layers and ws.regions are always those of the active canvas
        self.canvases = [{"id": "canvas-1", "name": "Map Canvas 1", "layers": self.layers,
                          "regions": self.regions, "settings": {}}]
        self.active_canvas = "canvas-1"
        self.orphans: list[Layer] = []       # layers of closed canvases: still in the project

    # ----- map canvases -----------------------------------------------------
    def canvas_entry(self, cid: str) -> dict:
        for c in self.canvases:
            if c["id"] == cid:
                return c
        raise KeyError(cid)

    def add_canvas(self, cid: str, name: str) -> None:
        """A new canvas starts empty, like ArcGIS Pro's New Map."""
        self.canvases.append({"id": cid, "name": name, "layers": [], "regions": [], "settings": {}})

    def rename_canvas(self, cid: str, name: str) -> None:
        self.canvas_entry(cid)["name"] = name

    def remove_canvas(self, cid: str) -> None:
        if len(self.canvases) > 1 and cid != self.active_canvas:
            gone = self.canvas_entry(cid)
            self.canvases.remove(gone)
            for l in gone["layers"]:                 # the layers stay in the project
                if not any(l in c["layers"] for c in self.canvases) and l not in self.orphans:
                    self.orphans.append(l)

    def canvases_for_save(self) -> list[dict]:
        """Each canvas as the backend stores it: its layers (top first) with visible and opacity."""
        out = []
        for c in self.canvases:
            live = c["id"] == self.active_canvas
            layers = []
            for l in c["layers"]:
                vis, op = (l.visible, l.opacity) if live else c["settings"].get(l.id, (l.visible, l.opacity))
                layers.append({"id": l.id, "visible": bool(vis), "opacity": max(0.0, min(1.0, op / 100))})
            out.append({"id": c["id"], "name": c["name"], "layers": layers,
                        "regions": [[list(pt) for pt in poly] for poly in c["regions"]]})
        return out

    def load_canvases(self, saved: list[dict], active: str | None) -> None:
        """Rebuild the canvases of an opened project from what the backend sent.
        Every loaded layer is in self.all_layers() at this point."""
        everything = {l.id: l for l in self.all_layers()}
        self.canvases, used = [], set()
        for c in saved:
            layers, settings = [], {}
            for ref in c.get("layers", []):
                l = everything.get(ref["id"])
                if l is None or any(l is x for x in layers):
                    continue
                layers.append(l)
                settings[l.id] = (bool(ref.get("visible", True)), int(round(float(ref.get("opacity", 1.0)) * 100)))
                used.add(l.id)
            regions = [[tuple(pt) for pt in poly] for poly in (c.get("regions") or [])]
            self.canvases.append({"id": c["id"], "name": c["name"], "layers": layers,
                                  "regions": regions, "settings": settings})
        self.orphans = [l for l in everything.values() if l.id not in used]
        if not self.canvases:
            self.canvases = [{"id": "canvas-1", "name": "Map Canvas 1", "layers": [], "regions": [], "settings": {}}]
        if active not in {c["id"] for c in self.canvases}:
            active = self.canvases[0]["id"]
        cur = self.canvas_entry(active)
        for l in cur["layers"]:
            if l.id in cur["settings"]:
                l.visible, l.opacity = cur["settings"][l.id]
        self.layers, self.regions, self.active_canvas = cur["layers"], cur["regions"], active

    def all_layers(self) -> list:
        """Every layer loaded in the project: the active canvas's first, then the others."""
        out = list(self.layers)
        for l in [l for c in self.canvases for l in c["layers"]] + self.orphans:
            if not any(l is o for o in out):
                out.append(l)
        return out

    def in_canvas(self, lid: str) -> bool:
        return any(l.id == lid for l in self.layers)

    def switch_canvas(self, cid: str) -> None:
        """Make another canvas the active one: ws.layers / ws.regions now point at its own lists."""
        if cid == self.active_canvas:
            return
        cur = self.canvas_entry(self.active_canvas)
        cur["settings"] = {l.id: (l.visible, l.opacity) for l in self.layers}
        new = self.canvas_entry(cid)
        for l in new["layers"]:
            if l.id in new["settings"]:
                l.visible, l.opacity = new["settings"][l.id]
        self.layers, self.regions = new["layers"], new["regions"]
        self.active_canvas = cid

    def add_layer_to_canvas(self, lid: str, cid: str) -> bool:
        """Drag a layer into another canvas. The layer is shared, not copied."""
        target = self.canvas_entry(cid)
        if any(l.id == lid for l in target["layers"]):
            return False
        src = next((l for l in self.all_layers() if l.id == lid), None)
        if src is None:
            return False
        target["layers"].insert(0, src)                  # a layer goes on top of its canvas
        if src in self.orphans:
            self.orphans.remove(src)
        if cid == self.active_canvas:
            src.visible = True
        else:
            target["settings"][lid] = (True, src.opacity)
        return True

    # ----- helpers ----------------------------------------------------------
    def layer(self, lid: str) -> Layer:
        for l in self.all_layers():
            if l.id == lid:
                return l
        raise KeyError(lid)

    def has_layer(self, lid: str) -> bool:
        return any(l.id == lid for l in self.layers)

    def rasters(self) -> list[Layer]:
        return [l for l in self.layers if l.group == "raster"]

    def apply_ramp(self, name: str) -> None:
        self.ramp_name = name
        lut = ramp_lut(RAMPS[name])
        for lyr in self.rasters():
            if lyr.data is None or lyr.id == "slope":
                continue
            z = lyr.data.astype(float)
            s = self.stats(lyr)
            lo, hi = s["min"], s["max"]
            t = np.clip((z - lo) / ((hi - lo) or 1.0), 0, 1)
            rgba = np.empty(z.shape + (4,), dtype=np.uint8)
            rgba[..., :3] = lut[(t * 255).astype(int)]
            rgba[..., 3] = 255
            lyr.rgba = np.ascontiguousarray(rgba)

    def ramp_stops(self) -> list[tuple[float, str]]:
        return RAMPS[self.ramp_name]

    def add_placeholder(self, name: str, group: str) -> Layer:
        n = sum(1 for l in self.layers if l.user_added) + 1
        kind = {"raster": "gray", "vector": "vector", "basemap": "base"}[group]
        lyr = Layer(f"user{n}", name, "Interface preview · no data", group, kind, True,
                    desc="Placeholder layer · data loading is not connected yet",
                    user_added=True)
        self.layers.append(lyr)
        return lyr

    def add_raster_image(
        self,
        layer_id: str,
        name: str,
        rgba: np.ndarray,
        source: str,
        metadata: dict,
        stats: dict,
    ) -> Layer:
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ValueError("Raster display image must be an RGBA array.")
        source_width = metadata.get("width")
        source_height = metadata.get("height")
        if not isinstance(source_width, int) or not isinstance(source_height, int):
            raise ValueError("Backend raster metadata is missing its dimensions.")
        if source_width <= 0 or source_height <= 0:
            raise ValueError("Backend returned invalid raster dimensions.")
        layer = Layer(
            id=layer_id,
            name=name,
            sub=f"{source_width} × {source_height} pixels",
            group="raster",
            kind="gray",
            visible=True,
            desc=source,
            rgba=np.ascontiguousarray(rgba),
            user_added=True,
            source_width=source_width,
            source_height=source_height,
            bounds=metadata.get("bounds"),
            crs=metadata.get("crs"),
            pixel_size=metadata.get("pixel_size"),
            pixel_size_m=metadata.get("pixel_size_m"),
            nodata=metadata.get("nodata"),
            _stats=stats,
        )
        self.layers.append(layer)
        return layer

    def add_contour_layer(
        self,
        layer_id: str,
        name: str,
        geojson: dict,
        source: Layer,
    ) -> Layer:
        if source.bounds is None or source.rgba is None:
            raise ValueError("The source raster is missing its display bounds or image.")
        min_x, min_y, max_x, max_y = source.bounds
        if max_x <= min_x or max_y <= min_y:
            raise ValueError("The source raster has invalid bounds.")
        height, width = source.rgba.shape[:2]
        lines: list[tuple[float, np.ndarray]] = []
        features = geojson.get("features")
        if not isinstance(features, list):
            raise ValueError("Backend returned invalid contour GeoJSON.")
        for feature in features:
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])
            if geometry.get("type") == "LineString":
                coordinates = [coordinates]
            elif geometry.get("type") != "MultiLineString":
                continue
            level = float(feature.get("properties", {}).get("elevation", 0.0))
            for coordinates_line in coordinates:
                points = np.asarray(coordinates_line, dtype=float)
                if points.ndim != 2 or points.shape[0] < 2 or points.shape[1] < 2:
                    continue
                pixels = np.column_stack((
                    (points[:, 0] - min_x) / (max_x - min_x) * width,
                    (max_y - points[:, 1]) / (max_y - min_y) * height,
                ))
                lines.append((level, pixels))
        layer = Layer(
            id=layer_id,
            name=name,
            sub=f"{len(lines)} contour lines",
            group="vector",
            kind="contours",
            visible=True,
            desc=f"Derived from {source.name}",
            vector_lines=lines,
            user_added=True,
            source_width=width,
            source_height=height,
            bounds=source.bounds,
            crs=source.crs,
        )
        self.layers.append(layer)
        return layer

    def extent_cells(self, only_visible: bool = True) -> tuple[float, float, float, float]:
        x1 = y1 = 0.0
        has_raster = False
        for lyr in self.rasters():
            if lyr.visible or not only_visible:
                shape = lyr.data.shape if lyr.data is not None else (
                    lyr.rgba.shape[:2] if lyr.rgba is not None else None
                )
                if shape is not None:
                    has_raster = True
                    x1 = max(x1, float(lyr.col0 + shape[1]))
                    y1 = max(y1, float(shape[0]))
        if not has_raster:
            return 0.0, 0.0, float(self.WIDTH), float(self.HEIGHT)
        return 0.0, 0.0, max(x1, 1.0), max(y1, 1.0)

    def stats(self, lyr: Layer) -> Optional[dict]:
        if lyr._stats is not None:
            return lyr._stats
        if lyr.data is None:
            return None
        if lyr._stats is None:
            z = lyr.data.astype(float)
            z = z[np.isfinite(z)]
            if z.size == 0:
                return None
            hist, edges = np.histogram(z, bins=30)
            lyr._stats = {
                "min": float(z.min()), "max": float(z.max()), "mean": float(z.mean()),
                "std": float(z.std()), "count": int(z.size), "hist": hist, "edges": edges,
            }
        return lyr._stats

    def sample(self, lyr: Layer, cx: float, cy: float) -> dict:
        """Pixel information under the pointer (cx, cy in workspace cells)."""
        easting = self.X0 + (np.floor(cx) + 0.5) * self.CELL
        northing = self.Y_TOP - (np.floor(cy) + 0.5) * self.CELL
        out = {"easting": easting, "northing": northing, "type": lyr.value_label,
               "unit": lyr.unit, "value": None, "col": None, "row": None}
        if lyr.data is None:
            return out
        col = int(np.floor(cx)) - lyr.col0
        row = int(np.floor(cy))
        out["col"], out["row"] = col, row
        if 0 <= row < lyr.data.shape[0] and 0 <= col < lyr.data.shape[1]:
            out["value"] = float(lyr.data[row, col])
        return out

    @staticmethod
    def polygon_area_m2(poly: list[tuple[float, float]], cell: float = 10.0) -> float:
        a = 0.0
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            a += x1 * y2 - x2 * y1
        return abs(a) / 2.0 * cell * cell

    def vector_summary(self, lyr: Layer) -> tuple[list[tuple[str, str, str]], list[tuple[str, str]]]:
        """(cards, property rows) for the statistics pane of non-raster layers."""
        if lyr.id == "regions" and self.regions:
            areas = [self.polygon_area_m2(p, self.CELL) / 1e6 for p in self.regions]
            cards = [("Features", str(len(self.regions)), ""),
                     ("Total area", fmt(sum(areas), 2), "km²"),
                     ("Largest", fmt(max(areas), 2), "km²"),
                     ("Smallest", fmt(min(areas), 2), "km²")]
            props = [("Geometry", "Polygon"), ("Coordinate system", self.CRS_NAME),
                     ("EPSG", str(self.EPSG)), ("Editable", "Yes")]
        elif lyr.id == "contours" and self.contours:
            lines = sum(len(l) for _, l in self.contours)
            cards = [("Levels", str(len(self.contours)), ""), ("Polylines", str(lines), ""),
                     ("Interval", DASH, "m"), ("Index every", DASH, "m")]
            props = [("Geometry", "Polyline"), ("Coordinate system", self.CRS_NAME),
                     ("EPSG", str(self.EPSG))]
        elif lyr.shapes and lyr.vec_info:
            m = lyr.vec_info.get("meta") or {}
            crs = str(m.get("crs") or DASH)
            epsg = crs.split(":", 1)[1] if crs.upper().startswith("EPSG:") else DASH
            cards = [("Features", f"{m.get('features', lyr.shapes['total']):,}", ""),
                     ("Vertices", f"{m.get('vertices', 0):,}", ""),
                     ("Geometry", str(m.get("geometry", DASH)), ""),
                     ("Fields", str(len(m.get("fields", []) or [])) if m.get("fields") is not None else DASH, "")]
            props = [("Source", str(lyr.vec_info.get("source") or DASH)), ("Coordinate system", crs), ("EPSG", epsg)]
        elif lyr.kind == "contours" and lyr.vector_lines:
            levels = {level for level, _ in lyr.vector_lines}
            crs = lyr.crs or DASH
            epsg = crs.split(":", 1)[1] if crs.upper().startswith("EPSG:") else DASH
            cards = [("Levels", str(len(levels)), ""), ("Polylines", str(len(lyr.vector_lines)), ""),
                     ("Interval", DASH, "m"), ("Index every", DASH, "m")]
            props = [("Geometry", "Polyline"), ("Coordinate system", crs), ("EPSG", epsg)]
        else:
            cards = [("Features", DASH, ""), ("Bands", DASH, ""), ("Size", DASH, ""),
                     ("Type", DASH, "")]
            props = [("Status", "No data loaded"), ("Coordinate system", DASH)]
        return cards, props


# ----------------------------------------------------------------------------
# small custom widgets
# ----------------------------------------------------------------------------
class RampBar(QWidget):
    """Colour ramp (vertical for the legend, horizontal under the histogram)."""

    def __init__(self, stops: list[tuple[float, str]], vertical: bool = False) -> None:
        super().__init__()
        self.stops, self.vertical = stops, vertical
        if vertical:
            self.setFixedSize(16, 78)
        else:
            self.setFixedHeight(10)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_stops(self, stops: list[tuple[float, str]]) -> None:
        self.stops = stops
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.bottomLeft(), r.topLeft()) if self.vertical \
            else QLinearGradient(r.topLeft(), r.topRight())
        for pos, col in self.stops:
            g.setColorAt(pos, QColor(col))
        p.setBrush(g)
        p.setPen(QPen(QColor("#b9cdd8"), 1))
        p.drawRoundedRect(r, 3, 3)


class HistogramWidget(QWidget):
    """30-bar histogram. Draws only the baseline when there are no values."""

    def __init__(self) -> None:
        super().__init__()
        self.values: list[float] = []
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, hist) -> None:
        self.values = [float(x) for x in hist]
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        base = h - 8
        p.setPen(QPen(QColor("#d5e3ea"), 1))
        p.drawLine(0, base, w, base)
        if not self.values:
            return
        n, peak = len(self.values), max(self.values) or 1.0
        step = w / n
        p.setPen(Qt.PenStyle.NoPen)
        for i, v in enumerate(self.values):
            bh = max(1.5, (v / peak) * (base - 6))
            p.setBrush(QColor("#94b9c9" if i < 8 else "#5892ae"))
            p.drawRoundedRect(QRectF(i * step + 1, base - bh, step - 2, bh), 1, 1)


def _repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


# ----------------------------------------------------------------------------
# generic settings form (used by ribbon tools, in the pane or in a dialog)
# ----------------------------------------------------------------------------
class SettingsForm(QWidget):
    """Builds a form from field specs.

    field = dict(type=combo|slider|spin|check|text|layer|layers|info, label=..., key=...,
                 options=[...], min=, max=, value=, step=, decimals=, suffix=)
    """

    def __init__(self, fields: list[dict], raster_names: list[str]) -> None:
        super().__init__()
        self._getters: dict[str, Callable[[], object]] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        for f in fields:
            kind = f.get("type", "text")
            label = f.get("label", "")
            key = f.get("key") or label.lower().replace(" ", "_").replace("/", "_")
            if kind == "info":
                lab = QLabel(f.get("text", label))
                lab.setWordWrap(True)
                lab.setObjectName("formInfo")
                root.addWidget(lab)
                continue
            if kind == "check":
                cb = AppCheckBox(label)
                cb.setChecked(bool(f.get("value", False)))
                root.addWidget(cb)
                self._getters[key] = cb.isChecked
                continue
            if label:
                cap = QLabel(label)
                cap.setObjectName("fieldLabel")
                root.addWidget(cap)
            if kind == "combo":
                w = QComboBox()
                w.addItems(f.get("options", []))
                if f.get("value") in f.get("options", []):
                    w.setCurrentText(f["value"])
                root.addWidget(w)
                self._getters[key] = w.currentText
            elif kind == "layer":
                w = QComboBox()
                w.addItems(raster_names)
                root.addWidget(w)
                self._getters[key] = w.currentText
            elif kind == "layers":
                boxes = []
                for name in raster_names:
                    cb = QCheckBox(name)
                    cb.setChecked(name in f.get("checked", raster_names[:1]))
                    root.addWidget(cb)
                    boxes.append(cb)
                self._getters[key] = lambda b=boxes: [x.text() for x in b if x.isChecked()]
            elif kind == "slider":
                row = QHBoxLayout()
                s = QSlider(Qt.Orientation.Horizontal)
                s.setRange(int(f.get("min", 0)), int(f.get("max", 100)))
                s.setValue(int(f.get("value", 50)))
                val = QLabel()
                val.setObjectName("sliderValue")
                val.setMinimumWidth(56)
                val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                suffix = f.get("suffix", "")
                s.valueChanged.connect(lambda v, l=val, sf=suffix: l.setText(f"{v}{sf}"))
                val.setText(f"{s.value()}{suffix}")
                row.addWidget(s, 1)
                row.addWidget(val)
                root.addLayout(row)
                self._getters[key] = s.value
            elif kind == "spin":
                dec = int(f.get("decimals", 0))
                if dec:
                    w = QDoubleSpinBox()
                    w.setDecimals(dec)
                else:
                    w = QSpinBox()
                w.setRange(f.get("min", 0), f.get("max", 10000))
                w.setValue(f.get("value", 0))
                w.setSingleStep(f.get("step", 1))
                if f.get("suffix"):
                    w.setSuffix(" " + f["suffix"])
                root.addWidget(w)
                self._getters[key] = w.value
            else:
                w = QLineEdit(str(f.get("value", "")))
                root.addWidget(w)
                self._getters[key] = w.text

    def values(self) -> dict:
        return {k: g() for k, g in self._getters.items()}


# ----------------------------------------------------------------------------
# left pane
# ----------------------------------------------------------------------------
class _Clickable(QFrame):
    clicked = pyqtSignal()

    def mousePressEvent(self, e) -> None:
        super().mousePressEvent(e)
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


LAYER_MIME = "application/x-agtaam-layer"


class LayerRow(_Clickable):
    visibilityToggled = pyqtSignal(str, bool)
    menuRequested = pyqtSignal(str, object)

    def mousePressEvent(self, e) -> None:
        self._press_pos = e.position().toPoint() if e.button() == Qt.MouseButton.LeftButton else None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        """Drag this layer onto a map canvas tab to show it in that canvas too."""
        start = getattr(self, "_press_pos", None)
        if start is not None and (e.position().toPoint() - start).manhattanLength() > 8:
            self._press_pos = None
            mime = QMimeData()
            mime.setData(LAYER_MIME, self.lid.encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.CopyAction)
            return
        super().mouseMoveEvent(e)

    def __init__(self, lyr: Layer, in_canvas: bool = True) -> None:
        super().__init__()
        self.lid = lyr.id
        self.setObjectName("layerRow")
        self.setProperty("selected", False)
        self.setProperty("outside", not in_canvas)      # loaded, but not shown in this canvas
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 4, 4)
        lay.setSpacing(8)
        self.check = AppCheckBox()
        self.check.setChecked(lyr.visible and in_canvas)
        self.check.setToolTip(f"Show {lyr.name}" if in_canvas else f"Add {lyr.name} to this canvas")
        self.check.toggled.connect(lambda v: self.visibilityToggled.emit(self.lid, v))
        sw = QLabel()
        sw.setObjectName("swatch")
        sw.setProperty("kind", lyr.kind)
        sw.setFixedSize(16, 16)
        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(lyr.name)
        name.setObjectName("layerName")
        sub = QLabel(lyr.sub)
        sub.setObjectName("layerSub")
        self.sub = sub
        text.addWidget(name)
        text.addWidget(sub)
        menu = QToolButton()
        menu.setObjectName("layerMenu")
        menu.setText("⋯")
        menu.setToolTip(f"Statistics for {lyr.name}")
        menu.setCursor(Qt.CursorShape.PointingHandCursor)
        menu.clicked.connect(lambda: self.menuRequested.emit(self.lid, menu.mapToGlobal(menu.rect().bottomLeft())))
        lay.addWidget(self.check)
        lay.addWidget(sw)
        lay.addLayout(text, 1)
        lay.addWidget(menu)
        self.setToolTip(lyr.name)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        _repolish(self)


class ContentsPane(QFrame):
    layerSelected = pyqtSignal(str)
    visibilityChanged = pyqtSignal(str, bool)
    statisticsRequested = pyqtSignal(str)
    zoomToLayerRequested = pyqtSignal(str)
    addLayerRequested = pyqtSignal()
    closeRequested = pyqtSignal()
    resetRequested = pyqtSignal()

    GROUPS = [("raster", "Raster Layers", "grid"), ("vector", "Vector Layers", "vector"),
              ("basemap", "Basemap Layers", "basemap")]

    def __init__(self, ws: SampleWorkspace) -> None:
        super().__init__()
        self.ws = ws
        self.setObjectName("contents")
        self.selected: Optional[str] = None
        self.collapsed: set[str] = set()
        self.rows: dict[str, LayerRow] = {}
        self.group_boxes: dict[str, QWidget] = {}
        self.legend_widgets: list = []

        # outer = QVBoxLayout(self)
        # outer.setContentsMargins(0, 0, 0, 0)
        # outer.setSpacing(0)

        # transparent wrapper -> small gap so the outline is visible
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(8, 8, 4, 8)
        wrapper.setSpacing(0)

# the actual outlined box (ArcMap-style separate panel)
        box = QFrame()
        box.setObjectName("contentsBox")
        wrapper.addWidget(box)

        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.setStyleSheet("""
    #contents {
        background: transparent;
        border: none;
    }
    #contentsBox {
        background: #f8fafb;
        border: 1px solid #8fa3b0;
        border-radius: 6px;
    }
    #contentsBox #paneTitle {
        background: #e6edf1;
        border: none;
        border-bottom: 1px solid #8fa3b0;
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
        min-height: 36px;
    }
    #contentsBox #contentsBottom {
        background: #eef3f6;
        border: none;
        border-top: 1px solid #c5d3db;
        border-bottom-left-radius: 5px;
        border-bottom-right-radius: 5px;
        min-height: 30px;
    }
""")

        title = QFrame()
        title.setObjectName("paneTitle")
        tl = QHBoxLayout(title)
        tl.setContentsMargins(14, 0, 8, 0)
        lab = QLabel("Layers")
        lab.setObjectName("paneTitleText")
        tl.addWidget(lab)
        tl.addStretch(1)
        
        close = self._icon_button("close", "Hide contents")
        close.clicked.connect(self.closeRequested)
    
        tl.addWidget(close)
        outer.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll, 1)

        self.rebuild()

    @staticmethod
    def _icon_button(name: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName("iconButton")
        b.setIcon(icon(name, "#244557", 18))
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    # ----- tree -------------------------------------------------------------
    def rebuild(self) -> None:
        body = QWidget()
        body.setObjectName("layerTree")
        v = QVBoxLayout(body)
        v.setContentsMargins(6, 0, 6, 10)
        v.setSpacing(2)
        self.rows.clear()
        self.group_boxes.clear()
        self.legend_widgets.clear()
        for gid, gname, gicon in self.GROUPS:
            members = [l for l in self.ws.all_layers() if l.group == gid]
            #  new lines added for making the layers column a bit dynamic
            head = _Clickable(body)
            head.setObjectName("groupHeading")
            head.setCursor(Qt.CursorShape.PointingHandCursor)

            hl = QHBoxLayout(head)
            hl.setContentsMargins(6, 5, 6, 5)
            hl.setSpacing(6)
            arrow = QLabel()
            arrow.setPixmap(pixmap("chevron_right" if gid in self.collapsed else "chevron", "#4b6573", 16))
            ic = QLabel()
            ic.setPixmap(pixmap(gicon, "#244557", 18))
            name = QLabel(gname)
            name.setObjectName("groupName")
            cnt = QLabel(str(len(members)))
            cnt.setObjectName("groupCount")
            hl.addWidget(arrow)
            hl.addWidget(ic)
            hl.addWidget(name)
            hl.addStretch(1)
            hl.addWidget(cnt)
            v.addWidget(head)

            box = QWidget(body)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(14, 0, 0, 4)
            bl.setSpacing(1)

            for lyr in members:
                if not members:
                    hint = QLabel(f"No {gname.lower()} added yet",box)
                    hint.setObjectName("emptyHint")
                    bl.addWidget(hint)

                row = LayerRow(lyr, self.ws.in_canvas(lyr.id))
                row.clicked.connect(lambda lid=lyr.id: self._row_clicked(lid))
                row.visibilityToggled.connect(self.visibilityChanged)
                row.menuRequested.connect(self._show_menu)
                row.set_selected(lyr.id == self.selected)
                self.rows[lyr.id] = row
                bl.addWidget(row)
                if lyr.id == "dem" and self.ws.stats(lyr):
                    bl.addWidget(self._legend(lyr))
                    #  adding this to  avoid the unwanted window display again and again
            box.setVisible(gid not in self.collapsed)
            self.group_boxes[gid] = box
            head.clicked.connect(lambda g=gid: self._toggle_group(g))
            v.addWidget(box)
            box.setVisible(gid not in self.collapsed)

        v.addStretch(1)
        self.scroll.setWidget(body)
        

    def _legend(self, lyr: Layer) -> QWidget:
        w = QFrame()
        w.setObjectName("legendBlock")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(34, 2, 8, 6)
        lay.setSpacing(3)
        cap = QLabel(f"{lyr.value_label} ({lyr.unit})")
        cap.setObjectName("legendCaption")
        lay.addWidget(cap)
        row = QHBoxLayout()
        self.legend_ramp = RampBar(self.ws.ramp_stops(), vertical=True)
        row.addWidget(self.legend_ramp)
        s = self.ws.stats(lyr)
        ticks = QVBoxLayout()
        for i, val in enumerate((s["max"], s["mean"], s["min"])):
            t = QLabel(fmt(val, 0))
            t.setObjectName("legendTick")
            ticks.addWidget(t)
            if i < 2:
                ticks.addStretch(1)
        row.addLayout(ticks)
        row.addStretch(1)
        lay.addLayout(row)
        return w

    def refresh_legend(self) -> None:
        if hasattr(self, "legend_ramp"):
            try:
                self.legend_ramp.set_stops(self.ws.ramp_stops())
            except RuntimeError:        # widget already deleted by a rebuild
                pass

    def _toggle_group(self, gid: str) -> None:
        if gid in self.collapsed:
            self.collapsed.discard(gid)
        else:
            self.collapsed.add(gid)
        QTimer.singleShot(0, self.rebuild)      # rebuild after the click event is fully processed  

    def _row_clicked(self, lid: str) -> None:
        self.select(lid)
        self.layerSelected.emit(lid)

    def _show_menu(self, lid: str, pos) -> None:
        self.select(lid)
        self.layerSelected.emit(lid)
        m = QMenu(self)
        m.addAction(icon("stats", "#244557", 18), "Layer statistics",
                    lambda: self.statisticsRequested.emit(lid))
        m.addAction(icon("zoom_layer", "#244557", 18), "Zoom to layer",
                    lambda: self.zoomToLayerRequested.emit(lid))
        m.exec(pos)

    # ----- public -----------------------------------------------------------
    def select(self, lid: str | None) -> None:
        self.selected = lid
        for k, r in self.rows.items():
            r.set_selected(k == lid)

    def set_visible(self, lid: str, on: bool) -> None:
        row = self.rows.get(lid)
        if row and row.check.isChecked() != on:
            row.check.blockSignals(True)
            row.check.setChecked(on)
            row.check.blockSignals(False)

    def set_sub(self, lid: str, text: str) -> None:
        if lid in self.rows:
            self.rows[lid].sub.setText(text)

# ----------------------------------------------------------------------------
def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear(item.layout())


class InspectorPane(QFrame):
    closeRequested = pyqtSignal()
    showStatsRequested = pyqtSignal()
    opacityChanged = pyqtSignal(str, int)
    toolRun = pyqtSignal(dict, dict)
    toolCancelled = pyqtSignal()

    def __init__(self, ws: SampleWorkspace) -> None:
        super().__init__()
        self.ws = ws
        self.setObjectName("inspector")

        # transparent wrapper -> small gap so the outline is visible
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(4, 8, 8, 8)
        wrapper.setSpacing(0)

        # the actual outlined box
        box = QFrame()
        box.setObjectName("inspectorBox")
        wrapper.addWidget(box)

        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.setStyleSheet("""
            #inspector {
        background: transparent;
        border: none;
            }
            #inspectorBox {
        background: #f8fafb;
        border: 1px solid #8fa3b0;
        border-radius: 6px;
            }
            #inspectorBox #paneTitle {
        background: #e6edf1;
        border: none;
        border-bottom: 1px solid #8fa3b0;
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
        min-height: 36px;
         }
            #inspectorBox QScrollArea {
        background: transparent;
        border: none;
        border-bottom-left-radius: 5px;
        border-bottom-right-radius: 5px;
         }
        """)

        title = QFrame()
        title.setObjectName("paneTitle")
        tl = QHBoxLayout(title)
        tl.setContentsMargins(14, 0, 8, 0)

        #  here name would be changed as layer statistics and properties
        self.title = QLabel("Layer Statistics & Properties")
        self.title.setObjectName("paneTitleText")
        tl.addWidget(self.title)
        tl.addStretch(1)
        b1 = ContentsPane._icon_button("stats", "Layer statistics")
        b1.clicked.connect(self.showStatsRequested)
        b2 = ContentsPane._icon_button("close", "Hide statistics")
        b2.clicked.connect(self.closeRequested)
        tl.addWidget(b1)
        tl.addWidget(b2)
        outer.addWidget(title)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.stats_scroll = QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.stack.addWidget(self.stats_scroll)

        self.tool_scroll = QScrollArea()
        self.tool_scroll.setWidgetResizable(True)
        self.tool_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.stack.addWidget(self.tool_scroll)
        self.current_layer: Optional[str] = None
        self.show_empty_state()

    # ----- statistics page --------------------------------------------------
    def show_empty_state(self) -> None:
        """Same layout as a loaded layer, with every value left blank."""
        self.current_layer = None
        self._render_stats(None)

    def show_layer(self, lyr: Layer) -> None:
        self.current_layer = lyr.id
        self._render_stats(lyr)

    def _render_stats(self, lyr: Optional[Layer]) -> None:
        #  here name would be changed as layer statistics & properties
        self.title.setText("Layer Statistics & Properties")
        self.stack.setCurrentWidget(self.stats_scroll)
        body = QWidget()
        body.setObjectName("inspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(14)

        # selected layer header
        trow = QHBoxLayout()
        sw = QLabel()
        sw.setObjectName("swatch")
        sw.setProperty("kind", lyr.kind if lyr else "gray")
        sw.setFixedSize(18, 18)
        name = QLabel(lyr.name if lyr else "No layer selected")
        name.setObjectName("selectedLayerTitle")
        name.setWordWrap(True)
        trow.addWidget(sw)
        trow.addWidget(name, 1)
        v.addLayout(trow)

        stats = self.ws.stats(lyr) if lyr else None
        has_values = bool(stats and stats["count"])
        is_raster_view = lyr is None or lyr.data is not None or lyr.group == "raster"

        if is_raster_view:
            unit = lyr.unit if lyr else ""
            v.addLayout(self._section_label("Statistics", unit))
            if has_values:
                cards = [("Minimum", fmt(stats["min"]), unit), ("Maximum", fmt(stats["max"]), unit),
                         ("Mean", fmt(stats["mean"]), unit), ("Std. deviation", fmt(stats["std"]), unit),
                         ("Median", fmt(stats["median"]), unit)
                         if stats.get("median") is not None else ("Median", DASH, "")]
            else:
                cards = [("Minimum", DASH, ""), ("Maximum", DASH, ""),
                         ("Mean", DASH, ""), ("Std. deviation", DASH, ""),
                         ("Median", DASH, "")]
            v.addLayout(self._card_grid(cards))

            v.addLayout(self._section_label(
                "Histogram", f"{stats['count']:,} pixels" if has_values else "0 pixels"))
            hist = HistogramWidget()
            if has_values:
                hist.set_values(stats["hist"])
            v.addWidget(hist)
            axis = QHBoxLayout()
            if has_values:
                labels = [fmt(stats["min"], 0), fmt(stats["mean"], 0), fmt(stats["max"], 0)]
            else:
                labels = [DASH, DASH, DASH]
            for i, text in enumerate(labels):
                lab = QLabel(text)
                lab.setObjectName("histAxis")
                axis.addWidget(lab)
                if i < 2:
                    axis.addStretch(1)
            v.addLayout(axis)
            if lyr is not None and lyr.id in ("dem", "east"):
                stops = self.ws.ramp_stops()
            elif lyr is not None and lyr.id == "slope":
                stops = SLOPE_RAMP
            else:
                stops = NEUTRAL_RAMP
            v.addWidget(RampBar(stops))

            if lyr is not None and lyr.group == "raster":
                dimensions = (
                    f"{lyr.source_width} × {lyr.source_height}"
                    if lyr.source_width is not None and lyr.source_height is not None
                    else (f"{lyr.data.shape[1]} × {lyr.data.shape[0]}"
                          if lyr.data is not None else DASH)
                )
                pixel_size = (
                    f"{lyr.pixel_size[0]:g} × {lyr.pixel_size[1]:g}"
                    if lyr.pixel_size is not None else f"{self.ws.CELL:g} × {self.ws.CELL:g} m"
                )
                crs = lyr.crs or (
                    self.ws.CRS_NAME if lyr.id in ("dem", "east") else DASH
                )
                epsg = crs.split(":", 1)[1] if crs.upper().startswith("EPSG:") else DASH
                nodata_count = stats.get("nodata_count") if stats else None
                bounds = (
                    ", ".join(f"{coordinate:g}" for coordinate in lyr.bounds)
                    if lyr.bounds is not None else DASH
                )
                rows = [("Coordinate system", crs), ("EPSG", epsg),
                        ("Pixel size", pixel_size), ("Dimensions", dimensions),
                        ("NoData pixels", str(nodata_count) if nodata_count is not None else DASH),
                        ("NoData value", str(lyr.nodata) if lyr.nodata is not None else DASH),
                        ("Bounds", bounds), ("Bands", "1")]
            else:
                rows = [("Coordinate system", DASH), ("EPSG", DASH), ("Pixel size", DASH),
                        ("Dimensions", DASH), ("NoData pixels", DASH),
                        ("NoData value", DASH), ("Bounds", DASH), ("Bands", DASH)]
            section = "Properties"
        else:
            cards, rows = self.ws.vector_summary(lyr)
            v.addLayout(self._section_label("Layer summary", ""))
            v.addLayout(self._card_grid(cards))
            section = "Properties"

        v.addLayout(self._section_label(section, ""))
        v.addWidget(self._prop_table(rows))

        v.addLayout(self._section_label("Display opacity", ""))
        orow = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(lyr.opacity if lyr else 100)
        slider.setEnabled(lyr is not None)
        val = QLabel(f"{lyr.opacity if lyr else 100}%")
        val.setObjectName("sliderValue")
        val.setMinimumWidth(44)
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if lyr is not None:
            def on_change(x: int, lid=lyr.id, label=val) -> None:
                label.setText(f"{x}%")
                self.opacityChanged.emit(lid, x)
            slider.valueChanged.connect(on_change)
        orow.addWidget(slider, 1)
        orow.addWidget(val)
        v.addLayout(orow)

        v.addStretch(1)
        self.stats_scroll.setWidget(body)

    def _section_label(self, text: str, right: str) -> QHBoxLayout:
        row = QHBoxLayout()
        a = QLabel(text.upper())
        a.setObjectName("sectionLabel")
        row.addWidget(a)
        row.addStretch(1)
        if right:
            b = QLabel(right)
            b.setObjectName("sectionRight")
            row.addWidget(b)
        return row

    def _card_grid(self, cards: list[tuple[str, str, str]]) -> QGridLayout:
        g = QGridLayout()
        g.setSpacing(8)
        for i, (label, value, unit) in enumerate(cards):
            card = QFrame()
            card.setObjectName("statCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(2)
            l = QLabel(label)
            l.setObjectName("statLabel")
            val = QLabel(f"{value} <span style='font-size:11px;color:#6f8794;font-weight:500'>{unit}</span>")
            val.setObjectName("statValue")
            val.setTextFormat(Qt.TextFormat.RichText)
            cl.addWidget(l)
            cl.addWidget(val)
            g.addWidget(card, i // 2, i % 2)
        return g

    def _prop_table(self, rows: list[tuple[str, str]]) -> QWidget:
        t = QFrame()
        t.setObjectName("propTable")
        l = QVBoxLayout(t)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        for i, (k, val) in enumerate(rows):
            r = QFrame()
            r.setObjectName("propRow")
            r.setProperty("last", i == len(rows) - 1)
            rl = QHBoxLayout(r)
            rl.setContentsMargins(10, 7, 10, 7)
            a = QLabel(k)
            a.setObjectName("propKey")
            b = QLabel(val)
            b.setObjectName("propValue")
            b.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            b.setWordWrap(True)
            rl.addWidget(a)
            rl.addWidget(b, 1)
            l.addWidget(r)
        return t

    # ----- tool settings page -----------------------------------------------
    def show_tool(self, tool: dict, raster_names: list[str]) -> None:
        self.title.setText("Tool Settings")
        self.stack.setCurrentWidget(self.tool_scroll)
        body = QWidget()
        body.setObjectName("inspectorBody")
        v = QVBoxLayout(body)
        v.setContentsMargins(16, 14, 16, 16)
        v.setSpacing(12)
        eyebrow = QLabel(tool.get("group_label", "TOOL").upper())
        eyebrow.setObjectName("eyebrow")
        v.addWidget(eyebrow)
        head = QHBoxLayout()
        ic = QLabel()
        ic.setPixmap(pixmap(tool.get("icon", "grid"), "#1f6f9a", 24))
        name = QLabel(tool["label"])
        name.setObjectName("selectedLayerTitle")
        head.addWidget(ic)
        head.addWidget(name, 1)
        v.addLayout(head)
        desc = QLabel(tool.get("tip", ""))
        desc.setObjectName("layerDesc")
        desc.setWordWrap(True)
        v.addWidget(desc)
        form = SettingsForm(tool.get("fields", []), raster_names)
        v.addWidget(form)
        buttons = QHBoxLayout()
        run = QPushButton(tool.get("run_label", "Run"))
        run.setObjectName("primaryButton")
        run.clicked.connect(lambda: self.toolRun.emit(tool, form.values()))
        cancel = QPushButton("Close")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.toolCancelled)
        buttons.addWidget(run, 1)
        buttons.addWidget(cancel)
        v.addLayout(buttons)
        note_text = (
            "Runs this analysis on the selected raster and adds the result as a new layer."
            if tool.get("handler") == "terrain_derivative"
            else "Interface preview: settings are captured but no processing is connected yet."
        )
        note = QLabel(note_text)
        note.setObjectName("paneFootnote")
        note.setWordWrap(True)
        v.addWidget(note)
        v.addStretch(1)
        self.tool_scroll.setWidget(body)


class MapBox(QFrame):
    """Wraps the map/DEM canvas in an outlined, ArcMap-style box."""

    def __init__(self, canvas: QWidget) -> None:
        super().__init__()
        self.setObjectName("mapOuter")

        # transparent wrapper -> gap so the outline is visible
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(4, 8, 4, 8)   # sides 4 to match the side panes
        wrapper.setSpacing(0)

        box = QFrame()
        box.setObjectName("mapBox")
        wrapper.addWidget(box)

        inner = QVBoxLayout(box)
        inner.setContentsMargins(1, 1, 1, 1)     # keeps the canvas off the border line
        inner.setSpacing(0)
        inner.addWidget(canvas)

        self.setStyleSheet("""
            #mapOuter {
                background: transparent;
                border: none;
            }
            #mapBox {
                background: #f8f9fa;
                border: 1px solid #8fa3b0;
                border-radius: 6px;
            }
        """)



class AppCheckBox(QCheckBox):
    """White checkbox with a dark border and tick, drawn in code (no image files)."""

    BOX = 16

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = self.BOX + 4
        if self.text():
            w += 8 + fm.horizontalAdvance(self.text())
        return QSize(w, max(self.BOX, fm.height()) + 6)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)      # whole row (box + text) is clickable

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on, enabled = self.isChecked(), self.isEnabled()
        y = (self.height() - self.BOX) / 2
        box = QRectF(1, y + 1, self.BOX - 2, self.BOX - 2)

        if not enabled:
            border, fill = "#ced4da", "#e9ecef"
        else:
            border = "#343a40" if (on or self.underMouse()) else "#868e96"
            fill = "#ffffff"
        p.setPen(QPen(QColor(border), 1.5))
        p.setBrush(QColor(fill))
        p.drawRoundedRect(box, 4, 4)

        if on:
            pen = QPen(QColor("#343a40" if enabled else "#adb5bd"), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            x0, y0 = box.left(), box.top()
            p.drawPolyline(QPolygonF([
                QPointF(x0 + 3, y0 + 7.5),
                QPointF(x0 + 6, y0 + 10.5),
                QPointF(x0 + 11, y0 + 4.5),
            ]))

        if self.text():
            p.setPen(QColor("#212529" if enabled else "#adb5bd"))
            p.drawText(
                QRectF(self.BOX + 8, 0, self.width() - self.BOX - 8, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self.text(),
            )