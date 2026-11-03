"""Terrain Editing logic.

Edits are NOT applied straight away. Each button queues an operation; Preview computes the
result; Apply creates a new "(edited)" layer. The original layer is never overwritten.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

import numpy as np

from core.editing.compare import compare as core_compare
from core.editing.fill_sinks import fill_sinks
from core.editing.flatten import flatten
from core.editing.raise_lower import raise_lower
from core.editing.regions import polygon_mask
from core.editing.smooth import smooth
from core.raster.crs import cell_size_meters
from core.raster.writer import write_geotiff
from core.stats import layer_stats
from shared.errors import BadRequest, NotFound
from shared.layer_store import add_raster_layer, get_raster_layer, layer_store

_lock = threading.RLock()


@dataclass
class Region:
    id: str
    name: str
    polygon: list
    selected: bool = True

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "polygon": self.polygon, "selected": self.selected}


@dataclass
class Session:
    regions: dict[str, Region] = field(default_factory=dict)
    ops: list[dict] = field(default_factory=list)
    preview: np.ndarray | None = None


_sessions: dict[str, Session] = {}

# Edit sessions belong to a layer: forget them when the layer (or the whole project) goes away.
layer_store.on_remove(lambda layer_id: _sessions.pop(layer_id, None))
layer_store.on_clear(_sessions.clear)


def _session(layer_id: str) -> Session:
    get_raster_layer(layer_id)                         # 404 / 400 if the layer is wrong
    with _lock:
        return _sessions.setdefault(layer_id, Session())


# ---- selection ----
def draw_region(layer_id: str, polygon, name: str | None) -> dict:
    s = _session(layer_id)
    raster = get_raster_layer(layer_id).raster
    if not polygon_mask(raster.data.shape, raster.transform, polygon).any():
        raise BadRequest("That region does not cover any raster cells.", code="empty_region")
    region = Region(uuid.uuid4().hex[:8], name or f"Region {len(s.regions) + 1}",
                    [list(p) for p in polygon])
    s.regions[region.id] = region
    s.preview = None
    return region.to_dict()


def list_regions(layer_id: str) -> dict:
    s = _session(layer_id)
    return {"count": len(s.regions), "regions": [r.to_dict() for r in s.regions.values()]}


def select_regions(layer_id: str, region_ids: list[str]) -> dict:
    s = _session(layer_id)
    unknown = [i for i in region_ids if i not in s.regions]
    if unknown:
        raise NotFound(f"Unknown region(s): {', '.join(unknown)}", code="region_not_found")
    for r in s.regions.values():
        r.selected = r.id in region_ids
    return list_regions(layer_id)


def delete_selected(layer_id: str) -> dict:
    s = _session(layer_id)
    gone = {i for i, r in s.regions.items() if r.selected}
    for i in gone:
        del s.regions[i]
    for op in s.ops:
        op["region_ids"] = [i for i in op["region_ids"] if i not in gone]
    s.ops = [op for op in s.ops if op["region_ids"]]
    s.preview = None
    return {"deleted": len(gone), **list_regions(layer_id)}


def clear_all(layer_id: str) -> dict:
    with _lock:
        _sessions[layer_id] = Session()
    get_raster_layer(layer_id)
    return {"count": 0, "regions": []}


# ---- modify terrain (queues operations) ----
def queue(layer_id: str, kind: str, params: dict, region_ids: list[str] | None) -> dict:
    s = _session(layer_id)
    ids = region_ids if region_ids is not None else [i for i, r in s.regions.items() if r.selected]
    if not ids:
        raise BadRequest("Draw or select a region first.", code="no_region")
    unknown = [i for i in ids if i not in s.regions]
    if unknown:
        raise NotFound(f"Unknown region(s): {', '.join(unknown)}", code="region_not_found")
    s.ops.append({"id": uuid.uuid4().hex[:8], "type": kind, "params": params, "region_ids": ids})
    s.preview = None
    return pending(layer_id)


def pending(layer_id: str) -> dict:
    s = _session(layer_id)
    return {"count": len(s.ops), "operations": s.ops, "has_preview": s.preview is not None}


# ---- compute ----
def _edited(layer_id: str) -> np.ndarray:
    s = _session(layer_id)
    if not s.ops:
        raise BadRequest("There are no edits yet.", code="no_edits")
    raster = get_raster_layer(layer_id).raster
    data = raster.data.copy()
    for op in s.ops:
        mask = np.zeros(data.shape, dtype=bool)
        for rid in op["region_ids"]:
            mask |= polygon_mask(data.shape, raster.transform, s.regions[rid].polygon)
        kind, p = op["type"], op["params"]
        if kind == "raise_lower":
            data = raise_lower(data, mask, p["amount"])
        elif kind == "smooth":
            data = smooth(data, mask, p["iterations"])
        elif kind == "flatten":
            data = flatten(data, mask, p.get("elevation"))
        elif kind == "fill_sinks":
            data = fill_sinks(data, mask)
    return data


def _cell_area(layer_id: str) -> float:
    dx, dy = cell_size_meters(get_raster_layer(layer_id).raster)
    return dx * dy


# ---- review ----
def preview(layer_id: str) -> dict:
    s = _session(layer_id)
    s.preview = _edited(layer_id)
    before = get_raster_layer(layer_id).raster.data
    return {"operations": len(s.ops),
            **core_compare(before, s.preview, _cell_area(layer_id)),
            "statistics_after": layer_stats.compute(s.preview)}


def compare(layer_id: str) -> dict:
    s = _session(layer_id)
    if s.preview is None:
        s.preview = _edited(layer_id)
    before = get_raster_layer(layer_id).raster.data
    return {"before": layer_stats.compute(before), "after": layer_stats.compute(s.preview),
            "difference": core_compare(before, s.preview, _cell_area(layer_id))}


def discard(layer_id: str) -> dict:
    s = _session(layer_id)
    s.ops, s.preview = [], None
    return {"discarded": True, **pending(layer_id)}


# ---- output ----
def apply(layer_id: str) -> dict:
    s = _session(layer_id)
    src = get_raster_layer(layer_id)
    data = s.preview if s.preview is not None else _edited(layer_id)
    diff = core_compare(src.raster.data, data, _cell_area(layer_id))
    out = add_raster_layer(src.raster.with_data(data), f"{src.name} (edited)",
                           derived_from=src.id, tool="terrain_edit")
    s.ops, s.preview = [], None
    return {"layer": out.info(), "statistics": layer_stats.compute(data), "extra": {"difference": diff}}


def export_edited(layer_id: str, path: str) -> dict:
    src = get_raster_layer(layer_id)
    s = _session(layer_id)
    data = s.preview if s.preview is not None else _edited(layer_id)
    return {"path": write_geotiff(src.raster.with_data(data), path)}
