"""Terrain Mosaic logic: pick DEMs, study the overlap, blend, apply."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.mosaic.difference import difference_map
from core.mosaic.grid import check_compatible
from core.mosaic.merge import mosaic
from core.mosaic.seamline import min_difference_seamline
from core.raster.model import Raster
from core.raster.writer import write_geotiff
from core.stats import layer_stats
from shared.errors import BadRequest
from shared.jobs import jobs
from shared.layer_store import add_raster_layer, add_vector_layer, get_raster_layer, layer_store


@dataclass
class MosaicSession:
    layer_ids: list[str] = field(default_factory=list)
    method: str = "feather"
    feather_pixels: int = 20
    preview: Raster | None = None


session = MosaicSession()
_lock = threading.RLock()


def _reset() -> None:
    session.layer_ids, session.method, session.feather_pixels, session.preview = [], "feather", 20, None


def _layer_removed(layer_id: str) -> None:
    if layer_id in session.layer_ids:
        session.layer_ids.remove(layer_id)
        session.preview = None


# The selection refers to layer ids, so it must follow the layers.
layer_store.on_clear(_reset)
layer_store.on_remove(_layer_removed)


def _selected_rasters() -> list[Raster]:
    if len(session.layer_ids) < 2:
        raise BadRequest("Select at least two DEMs first.", code="no_selection")
    return [get_raster_layer(i).raster for i in session.layer_ids]


def _pair(layer_a: str | None, layer_b: str | None):
    if layer_a and layer_b:
        ids = [layer_a, layer_b]
    elif len(session.layer_ids) >= 2:
        ids = session.layer_ids[:2]
    else:
        raise BadRequest("Give layer_a and layer_b, or select DEMs first.", code="no_selection")
    return [get_raster_layer(i) for i in ids]


# ---- input ----
def _compat(rasters: list[Raster]) -> dict:
    try:
        check_compatible(rasters)
        return {"compatible": True, "problem": None}
    except ValueError as exc:
        return {"compatible": False, "problem": str(exc)}


def select_dems(layer_ids: list[str]) -> dict:
    layers = [get_raster_layer(i) for i in layer_ids]          # validates every id
    with _lock:
        session.layer_ids = list(layer_ids)
        session.preview = None
    return {"layer_ids": layer_ids, "names": [l.name for l in layers],
            **_compat([l.raster for l in layers])}


def get_selection() -> dict:
    layers = [get_raster_layer(i) for i in session.layer_ids]
    return {"layer_ids": session.layer_ids, "names": [l.name for l in layers],
            **(_compat([l.raster for l in layers]) if len(layers) > 1 else {"compatible": None, "problem": None})}


# ---- overlap analysis ----
def make_difference_map(layer_a: str | None, layer_b: str | None) -> dict:
    a, b = _pair(layer_a, layer_b)
    diff, stats = difference_map(a.raster, b.raster)
    out = add_raster_layer(diff, f"Difference {a.name} - {b.name}", derived_from=a.id, tool="difference_map")
    return {"layer": out.info(), "statistics": layer_stats.compute(diff.data), "extra": stats}


def make_seamline(layer_a: str | None, layer_b: str | None) -> dict:
    a, b = _pair(layer_a, layer_b)
    feature = min_difference_seamline(a.raster, b.raster)
    out = add_vector_layer({"type": "FeatureCollection", "features": [feature]},
                           f"Seamline {a.name} / {b.name}", derived_from=a.id, tool="seamline")
    return {"layer": out.info(), "statistics": None, "extra": {"seamline": feature}}


# ---- blend / preview / apply ----
def get_blend() -> dict:
    return {"method": session.method, "feather_pixels": session.feather_pixels}


def set_blend(method: str, feather_pixels: int) -> dict:
    session.method, session.feather_pixels = method, feather_pixels
    session.preview = None
    return get_blend()


def _summary(r: Raster) -> dict:
    return {"width": r.width, "height": r.height, "bounds": list(r.bounds),
            "method": session.method, "statistics": layer_stats.compute(r.data)}


def _build() -> Raster:
    return mosaic(_selected_rasters(), session.method, session.feather_pixels)


def preview(background: bool) -> dict:
    _selected_rasters()                                     # fail fast on a bad selection
    if not background:
        session.preview = _build()
        return _summary(session.preview)

    def work(report):
        report(0.1, "Merging DEMs")
        session.preview = _build()
        report(0.9, "Computing statistics")
        return _summary(session.preview)

    return {"job_id": jobs.submit("mosaic preview", work)}


def apply() -> dict:
    result = session.preview if session.preview is not None else _build()
    first = get_raster_layer(session.layer_ids[0])
    out = add_raster_layer(result, "Mosaic", derived_from=first.id, tool="mosaic")
    session.preview = None
    return {"layer": out.info(), "statistics": layer_stats.compute(result.data)}


def export_elevations(path: str) -> dict:
    result = session.preview if session.preview is not None else _build()
    return {"path": write_geotiff(result, path)}
