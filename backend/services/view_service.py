"""View tab logic: navigation, panes, appearance, display layers."""
from __future__ import annotations

import math
import uuid

from core.raster.crs import cell_size_meters
from core.raster.model import Raster
from core.render.colour_ramp import RAMPS
from core.render.map_image import render_png
from core.terrain.contours import contour_lines
from core.terrain.hillshade import compute_hillshade
from core.terrain.slope import compute_slope
from config import get_settings
from shared.errors import BadRequest, NotFound
from shared.layer_store import get_raster_layer, layer_store
from shared.project_store import project


def _ws() -> dict:
    return project.workspace


# ---- navigate ----
def _union_bounds(rasters: list[Raster]):
    b = [r.bounds for r in rasters]
    return (min(x[0] for x in b), min(x[1] for x in b), max(x[2] for x in b), max(x[3] for x in b))


def full_extent() -> dict:
    rasters = [l.raster for l in layer_store.list("raster") if l.visible]
    if not rasters:
        raise BadRequest("There are no visible raster layers.", code="no_layers")
    bounds = _union_bounds(rasters)
    _ws()["viewport"]["center"] = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    return {"bounds": bounds, "viewport": _ws()["viewport"]}


def zoom_to_layer(layer_id: str) -> dict:
    layer = layer_store.get(layer_id)
    if layer.raster is not None:
        bounds = layer.raster.bounds
    elif layer.geojson is not None:
        xs, ys = [], []
        _collect(layer.geojson, xs, ys)
        if not xs:
            raise BadRequest("The vector layer has no coordinates.", code="empty_layer")
        bounds = (min(xs), min(ys), max(xs), max(ys))
    else:
        raise BadRequest("Basemap layers have no extent.", code="no_extent")
    _ws()["viewport"]["center"] = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
    return {"layer_id": layer_id, "bounds": bounds, "viewport": _ws()["viewport"]}


def _collect(node, xs: list, ys: list) -> None:
    if isinstance(node, dict):
        for key in ("features", "geometries"):
            for item in node.get(key, []):
                _collect(item, xs, ys)
        if "geometry" in node and node["geometry"]:
            _collect(node["geometry"], xs, ys)
        if "coordinates" in node:
            _collect(node["coordinates"], xs, ys)
    elif isinstance(node, list):
        if len(node) >= 2 and all(isinstance(v, (int, float)) for v in node[:2]):
            xs.append(node[0])
            ys.append(node[1])
        else:
            for item in node:
                _collect(item, xs, ys)


def zoom(factor: float, direction: str) -> dict:
    vp = _ws()["viewport"]
    if vp["scale"]:
        vp["scale"] = vp["scale"] / factor if direction == "in" else vp["scale"] * factor
    return vp


def update_viewport(center, scale) -> dict:
    vp = _ws()["viewport"]
    if center is not None:
        vp["center"] = list(center)
    if scale is not None:
        vp["scale"] = scale
    return vp


def set_mode(mode: str) -> dict:
    _ws()["mode"] = mode
    return {"mode": mode}


# ---- panes ----
def get_panes() -> dict:
    return _ws()["panes"]


def set_pane(name: str, visible: bool) -> dict:
    panes = _ws()["panes"]
    if name not in panes:
        raise NotFound(f"Unknown pane '{name}'. Choose from {sorted(panes)}.", code="pane_not_found")
    panes[name] = visible
    return panes


# ---- appearance ----
def get_appearance() -> dict:
    return _ws()["appearance"]


def update_appearance(fields: dict) -> dict:
    if "colour_ramp" in fields and fields["colour_ramp"] not in RAMPS:
        raise BadRequest(f"Unknown colour ramp. Choose from {sorted(RAMPS)}.", code="bad_ramp")
    _ws()["appearance"].update(fields)
    return _ws()["appearance"]


def colour_ramps() -> list[str]:
    return sorted(RAMPS)


# ---- display ----
def get_display() -> dict:
    return {**_ws()["display"], "annotations": _ws()["annotations"]}


def update_display(fields: dict) -> dict:
    _ws()["display"].update(fields)
    return get_display()


def _png(raster: Raster, ramp: str, vmin=None, vmax=None) -> bytes:
    return render_png(raster, ramp, vmin, vmax, get_settings().max_png_pixels)


def hillshade_image(layer_id: str, azimuth: float, altitude: float, z_factor: float) -> bytes:
    r = get_raster_layer(layer_id).raster
    dx, dy = cell_size_meters(r)
    shade = compute_hillshade(r.data, dx, dy, azimuth, altitude, z_factor)
    return _png(r.with_data(shade), "greys", 0, 255)


def slope_image(layer_id: str, ramp: str) -> bytes:
    r = get_raster_layer(layer_id).raster
    dx, dy = cell_size_meters(r)
    return _png(r.with_data(compute_slope(r.data, dx, dy)), ramp, 0, 60)


def contours(layer_id: str, interval: float, base: float) -> dict:
    return contour_lines(get_raster_layer(layer_id).raster, interval, base)


def reference_grid(layer_id: str, spacing: float) -> dict:
    """Grid lines every `spacing` (in the layer's units) as GeoJSON."""
    if spacing <= 0:
        raise BadRequest("spacing must be positive.", code="bad_spacing")
    minx, miny, maxx, maxy = get_raster_layer(layer_id).raster.bounds
    x0, y0 = math.ceil(minx / spacing) * spacing, math.ceil(miny / spacing) * spacing
    nx, ny = int((maxx - x0) // spacing) + 1, int((maxy - y0) // spacing) + 1
    if nx * ny > 10_000 or nx + ny > 400:
        raise BadRequest("That spacing would draw too many grid lines.", code="grid_too_dense")
    feats = []
    for i in range(nx):
        x = x0 + i * spacing
        feats.append({"type": "Feature", "properties": {"axis": "x", "value": x},
                      "geometry": {"type": "LineString", "coordinates": [[x, miny], [x, maxy]]}})
    for j in range(ny):
        y = y0 + j * spacing
        feats.append({"type": "Feature", "properties": {"axis": "y", "value": y},
                      "geometry": {"type": "LineString", "coordinates": [[minx, y], [maxx, y]]}})
    return {"type": "FeatureCollection", "features": feats}


def add_annotation(x: float, y: float, text: str) -> dict:
    note = {"id": uuid.uuid4().hex[:8], "x": x, "y": y, "text": text}
    _ws()["annotations"].append(note)
    return note


def remove_annotation(note_id: str) -> None:
    notes = _ws()["annotations"]
    kept = [n for n in notes if n["id"] != note_id]
    if len(kept) == len(notes):
        raise NotFound(f"Annotation '{note_id}' does not exist.", code="annotation_not_found")
    _ws()["annotations"] = kept
