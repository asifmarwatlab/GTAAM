"""Icon generator.

Every icon in the interface is a 24x24 stroke path (same style as the original
HTML design: stroke-width 1.55, round caps/joins).  Add a new icon by adding
one line to ICONS and then use ``icon("name")`` anywhere.
"""

from __future__ import annotations
from functools import lru_cache
from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

DEFAULT_COLOR = "#D5E6EF56"
ACCENT_COLOR = "#d4dce1c8"
WHITE = "#ffffff"

# name -> SVG path data (24 x 24 grid)
ICONS: dict[str, str] = {
    # --- taken directly from the original HTML -------------------------------
    "grid": "M3 3h18v18H3ZM3 9h18M3 15h18M9 3v18M15 3v18",
    "difference": "M3 4h8v16H3ZM13 4h8v16h-8M6 8h2M6 12h2M6 16h2M16 12h2",
    "seamline": "M3 4h18v16H3ZM10 4l5 4-6 5 6 7",
    "blend": "M9 3a8 8 0 1 0 0 16M15 5a8 8 0 1 1 0 16M12 5v14",
    "mosaic": "M3 3h12v12H3ZM9 9h12v12H9M15 3v6M3 15h6",
    "check": "M4 12l5 5L20 6",
    "export": "M5 13v8h14v-8M12 16V3M7 8l5-5 5 5",
    "search": "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Zm5-1.5L21 21",
    "plus": "M12 5v14M5 12h14",
    "minus": "M5 12h14",
    "close": "M6 6l12 12M18 6 6 18",
    "save": "M5 3h13l3 3v15H3V3h2Zm2 0v7h10V3M7 21v-7h10v7M14 5h1",
    "fullscreen": "M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5",
    "layers": "m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 16l9 5 9-5",
    "vector": "M5 4h4v4H5ZM16 15h4v4h-4ZM7 8l11 7M4 17h4v4H4ZM9 6l8-3",
    "terrain": "m2 19 7-13 5 9 3-5 5 9ZM7 10l2 3 2-3",
    "stats": "M4 20V12h4v8ZM10 20V7h4v13ZM16 20V3h4v17",
    "reset": "M3 10a9 9 0 1 1 1 7M3 4v6h6",
    "chevron": "m7 9 5 5 5-5",
    "chevron_right": "m9 7 5 5-5 5",
    "bookmark":"M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z",
    "swipe": "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M12 5v14 M8.5 9.5L6 12l2.5 2.5 M15.5 9.5L18 12l-2.5 2.5",
    "crosshair": "M3 3h7M3 3v7M21 3h-7M21 3v7M3 21h7M3 21v-7M21 21h-7M21 21v-7M8 12h8M12 8v8",
    # --- extra icons in the same visual style -------------------------------
    "folder": "M3 7h6l2 2h10v11H3Z",
    "file_new": "M6 3h8l4 4v14H6ZM14 3v4h4M12 11v6M9 14h6",
    "file_open": "M3 7h6l2 2h10v3M3 7v13h15l3-8H8l-3 8",
    "save_as": "M5 3h13l3 3v8M5 3H3v18h9M7 3v7h10V3M16 19h6M19 16v6",
    "image": "M3 4h18v16H3ZM3 16l5-5 5 5 3-3 5 5M15 8.5h.01",
    "raster_add": "M3 3h14v14H3ZM3 8.5h14M3 12.5h14M8.5 3v14M12.5 3v14M19 15v6M16 18h6",
    "vector_add": "M4 4h4v4H4ZM14 12h4v4h-4ZM6 8l8 6M19 4v6M16 7h6",
    "basemap": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "sliders": "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4",
    "ruler": "M3 16 16 3l5 5L8 21ZM7 15l2 2M10 12l2 2M13 9l2 2",
    "area": "M5 7l9-3 6 7-5 9-9-3ZM5 7h.01M14 4h.01M20 11h.01M15 20h.01M6 17h.01",
    "profile": "M3 20h18M3 20V4M6 16l4-5 3 3 5-8",
    "sun": "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4",
    "slope": "M3 20h18L3 5ZM9 20a6 6 0 0 0-3.5-5.4",
    "compass": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM15.5 8.5 13.5 13.5 8.5 15.5 10.5 10.5Z",
    "contours": "M3 8c4-4 8 2 12-1s5 0 6 2M3 14c4-4 8 2 12-1s5 0 6 2M3 20c4-4 8 2 12-1s5 0 6 2",
    "clip": "M6 3v15h15M3 6h15v15",
    "resample": "M4 4h7v7H4ZM13 13h7v7h-7ZM14 4h6v6M10 20H4v-6",
    "reproject": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM3 12h6M15 12h6M17 9l3 3-3 3",
    "cursor": "M5 3l14 8-6 2-2 6Z",
    "info": "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v6M12 7.5h.01",
    "table": "M3 4h18v16H3ZM3 10h18M9 4v16",
    "draw": "M5 6l10-3 5 8-6 9-9-4ZM5 6h.01M15 3h.01M20 11h.01M14 20h.01M5 16h.01",
    "select": "M4 4h4M12 4h4M20 4v4M20 12v4M20 20h-4M12 20H8M4 20v-4M4 12V8",
    "trash": "M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6",
    "raise": "M12 19V5M6 11l6-6 6 6",
    "lower": "M12 5v14M6 13l6 6 6-6",
    "smooth": "M3 12c3-6 6-6 9 0s6 6 9 0",
    "flatten": "M3 8h18M3 12h18M3 16h18",
    "drop": "M12 3s6 7 6 11a6 6 0 0 1-12 0c0-4 6-11 6-11Z",
    "eye": "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "compare": "M12 3v18M3 6h6v12H3ZM15 6h6v12h-6Z",
    "undo": "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3",
    "hand": "M8 12V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v8c0 4-2 7-6 7s-5-2-6-4l-2-4 1.5-1L8 15",
    "panel_left": "M3 4h18v16H3ZM9 4v16",
    "panel_right": "M3 4h18v16H3ZM15 4v16",
    "north": "M12 3l5 18-5-4-5 4Z",
    "scalebar": "M3 16h18M3 12v8M12 14v4M21 12v8",
    "palette": "M12 3a9 9 0 1 0 0 18c1.5 0 2-1 2-2s-1-2 0-3 2 0 4-1a9 9 0 0 0-6-12ZM7.5 11h.01M10 7h.01M15 7h.01",
    "sparkle": "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2Z",
    "database": "M4 6c0-2 16-2 16 0v12c0 2-16 2-16 0ZM4 6c0 2 16 2 16 0M4 12c0 2 16 2 16 0",
    "keyboard": "M3 6h18v12H3ZM7 10h.01M11 10h.01M15 10h.01M7 14h10",
    "gear": "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1",
    "exit": "M10 4H4v16h6M15 8l4 4-4 4M19 12H9",
    "annotation": "M4 5h16v10H9l-5 4Z",
    "label": "M3 5h12l6 7-6 7H3Z",
    "zoom_layer": "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM15.5 15.5 21 21M10.5 8v5M8 10.5h5",
    "wand": "M4 20 16 8M14 4l1 2 2 1-2 1-1 2-1-2-2-1 2-1Z",
    "file_json": "M6 3h8l4 4v14H6ZM14 3v4h4M9 12c-1 0-1 1-1 2s0 2 1 2M15 12c1 0 1 1 1 2s0 2-1 2",
}


# icons that are not drawn on the default 24 x 24 grid
VIEWBOX: dict[str, int] = {"brand": 32}


def _svg(path_d: str, color: str, stroke: float = 1.55, box: int = 24) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round"><path d="{path_d}"/></svg>'
    ).encode("utf-8")


def _device_ratio() -> float:
    app = QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    return float(screen.devicePixelRatio()) if screen else 1.0


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = DEFAULT_COLOR, size: int = 24, stroke: float = 1.55) -> QPixmap:
    """Render an icon to a crisp (HiDPI-aware) pixmap."""
    path_d = ICONS.get(name, ICONS["grid"])
    ratio = _device_ratio()
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(_svg(path_d, color, stroke, VIEWBOX.get(name, 24))))
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px.width(), px.height()))
    painter.end()
    px.setDevicePixelRatio(ratio)
    return px


@lru_cache(maxsize=512)
def icon(name: str, color: str = DEFAULT_COLOR, size: int = 24) -> QIcon:
    """QIcon with normal, active and disabled states."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    ic.addPixmap(pixmap(name, ACCENT_COLOR, size), QIcon.Mode.Active)
    ic.addPixmap(pixmap(name, "#a9bbc5", size), QIcon.Mode.Disabled)
    return ic


def brand_pixmap(color: str = WHITE, size: int = 30) -> QPixmap:
    """The A-GTAAM mountain logo from the title bar."""
    return pixmap("brand", color, size, 2.0)


# the logo (two paths in the original) is registered separately
ICONS["brand"] = "M2 25 13 6l6 10 4-6 8 15ZM9 13l4 3 3-3M21 14l3 3 2-2"
