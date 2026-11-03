"""Tools tab logic: data management, inspection, options."""
from __future__ import annotations

import platform
import sys

import numpy as np

from core.raster.clip import clip as core_clip
from core.raster.metadata import file_metadata, raster_properties
from core.raster.nodata import fill_nodata as core_fill
from core.raster.reproject import reproject as core_reproject
from core.raster.resample import resample as core_resample
from core.raster.sampling import sample_nearest
from core.raster.utils import num
from core.render.colour_ramp import RAMPS
from core.stats import layer_stats
from config import get_settings
from shared.errors import BadRequest
from shared.layer_store import Layer, add_raster_layer, get_raster_layer
from shared.project_store import project


def _result(src: Layer, raster, tool: str, label: str) -> dict:
    out = add_raster_layer(raster, f"{src.name} - {label}", derived_from=src.id, tool=tool)
    return {"layer": out.info(), "statistics": layer_stats.compute(raster.data)}


# ---- data management ----
def clip(layer_id: str, bounds) -> dict:
    src = get_raster_layer(layer_id)
    return _result(src, core_clip(src.raster, bounds), "clip", "clipped")


def resample(layer_id: str, cell_size: float, method: str) -> dict:
    src = get_raster_layer(layer_id)
    return _result(src, core_resample(src.raster, cell_size, method), "resample",
                   f"resampled {cell_size:g}")


def reproject(layer_id: str, epsg: int, method: str) -> dict:
    src = get_raster_layer(layer_id)
    return _result(src, core_reproject(src.raster, epsg, method), "reproject", f"EPSG {epsg}")


def fill_nodata(layer_id: str, max_iterations: int) -> dict:
    src = get_raster_layer(layer_id)
    filled = core_fill(src.raster.data, max_iterations)
    return _result(src, src.raster.with_data(filled), "fill_nodata", "filled")


# ---- inspect ----
def identify(layer_id: str, x: float, y: float) -> dict:
    layer = get_raster_layer(layer_id)
    r = layer.raster
    row, col = r.xy_to_rowcol(x, y)
    row, col = int(row), int(col)
    inside = 0 <= row < r.height and 0 <= col < r.width
    value = num(sample_nearest(r, [x], [y])[0]) if inside else None
    cx, cy = (float(v) for v in r.rowcol_to_xy(row, col)) if inside else (None, None)
    return {"layer": layer.name, "easting": x, "northing": y, "inside": inside,
            "row": row if inside else None, "col": col if inside else None,
            "value": value, "is_nodata": inside and value is None,
            "pixel_centre": [cx, cy] if inside else None}


def properties(layer_id: str) -> dict:
    return raster_properties(get_raster_layer(layer_id).raster)


def metadata(layer_id: str) -> dict:
    layer = get_raster_layer(layer_id)
    if layer.source is None:
        return {"file": None, "note": "Derived layer - it only exists in memory until exported.",
                "derived_from": layer.derived_from, "tool": layer.tool}
    return file_metadata(layer.source)


# ---- workspace ----
def get_options() -> dict:
    return project.workspace["options"]


def update_options(fields: dict) -> dict:
    if "default_ramp" in fields and fields["default_ramp"] not in RAMPS:
        raise BadRequest(f"Unknown colour ramp. Choose from {sorted(RAMPS)}.", code="bad_ramp")
    project.workspace["options"].update(fields)
    return project.workspace["options"]


SHORTCUTS = [
    {"keys": "Ctrl+K", "action": "Search tools"},
    {"keys": "Ctrl+N", "action": "New project"},
    {"keys": "Ctrl+O", "action": "Open project"},
    {"keys": "Ctrl+S", "action": "Save project"},
    {"keys": "Ctrl+Shift+S", "action": "Save project as"},
    {"keys": "F11", "action": "Fullscreen"},
    {"keys": "+ / -", "action": "Zoom in / out"},
    {"keys": "Home", "action": "Full extent"},
]


def shortcuts() -> list[dict]:
    return SHORTCUTS


def about() -> dict:
    s = get_settings()
    return {"name": s.app_name, "version": s.app_version, "api_prefix": s.api_prefix,
            "python": sys.version.split()[0], "platform": platform.platform(),
            "numpy": np.__version__}
