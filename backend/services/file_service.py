"""File tab logic: projects, adding data, exporting, workspace."""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path

from core.raster._deps import require_rasterio
from core.raster.reader import read_raster
from core.raster.writer import write_geotiff
from core.vector.reader import SUPPORTED as SUPPORTED_VECTOR, read_vector
from core.render.map_image import render_png
from core.stats import histogram, layer_stats
from core.vector.frame import to_cells
from core.vector.hit import top_feature_at
from config import get_settings
from shared.errors import BadRequest
from shared.layer_store import (Layer, add_raster_layer, add_vector_layer, get_raster_layer,
                                    layer_store)
from shared.project_store import project


# ---- project ----
def project_info() -> dict:
    return project.info()


def new_project(name: str) -> dict:
    project.new(name)
    return project.info()


def open_project(path: str) -> dict:
    """Open a project. The answer carries every layer (rasters with their display data), so a
    window can redraw the whole project from this one reply."""
    result = project.load(path)
    result["layers"] = [{**l.info(), "display": layer_display(l.id)} if l.kind == "raster" else l.info()
                        for l in layer_store.list()]
    return result


def save_project(path: str | None, gui: dict | None = None, name: str | None = None,
                 canvases: list[dict] | None = None, active_canvas: str | None = None) -> dict:
    return project.save(path, gui, name, canvases, active_canvas)


# ---- add data ----
def add_raster(path: str, name: str | None) -> dict:
    raster = read_raster(path)
    return add_raster_layer(raster, name or Path(path).stem, source=str(Path(path))).info()


def add_vector(path: str, name: str | None) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Vector file not found: {path}")
    if p.suffix.lower() not in SUPPORTED_VECTOR:
        raise BadRequest(f"Unsupported vector format '{p.suffix}'. "
                         f"Supported: {', '.join(SUPPORTED_VECTOR)}.", code="unsupported_format")
    try:
        data = read_vector(p)
    except ImportError as exc:
        raise BadRequest(str(exc), code="missing_dependency") from exc
    except ValueError as exc:
        raise BadRequest(str(exc), code="bad_vector") from exc
    layer = add_vector_layer(data, name or p.stem, source=str(p))
    layer.meta.update(_vector_facts(data))
    return layer.info()


def _walk(coords):
    """Yield every [x, y, ...] position inside a GeoJSON coordinates array."""
    if coords and isinstance(coords[0], (int, float)):
        yield coords
    else:
        for c in coords or []:
            yield from _walk(c)


def _vector_facts(data: dict) -> dict:
    """Feature count, geometry type, vertex count and bounds of a GeoJSON collection."""
    kinds: set[str] = set()
    xs: list[float] = []
    ys: list[float] = []
    count = 0
    for f in data.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") == "GeometryCollection":
            geoms = g.get("geometries", [])
        else:
            geoms = [g]
        for gg in geoms:
            if not gg.get("type"):
                continue
            kinds.add(gg["type"].replace("Multi", ""))
            for pos in _walk(gg.get("coordinates")):
                xs.append(float(pos[0]))
                ys.append(float(pos[1]))
                count += 1
    facts = {"features": len(data.get("features", [])), "vertices": count,
             "geometry": "/".join(sorted(kinds)) or "Unknown", "crs": "EPSG:4326"}
    if xs:
        facts["bounds"] = [min(xs), min(ys), max(xs), max(ys)]
    return facts


def add_basemap(name: str, url_template: str, attribution: str | None) -> dict:
    layer = Layer(name=name, kind="basemap", source=url_template,
                  meta={"attribution": attribution} if attribution else {})
    return layer_store.add(layer).info()


def list_layers() -> list[dict]:
    return [l.info() for l in layer_store.list()]


def update_layer(layer_id: str, fields: dict) -> dict:
    return layer_store.update(layer_id, **fields).info()


def reorder_layers(ids: list[str]) -> list[dict]:
    layer_store.reorder(ids)
    return list_layers()


def remove_layer(layer_id: str) -> None:
    layer_store.remove(layer_id)


def layer_geojson(layer_id: str, crs: str | None = None) -> dict:
    """The layer's GeoJSON. With `crs` (e.g. "EPSG:32643") a file you added (which is stored
    in EPSG:4326) is converted to that system, so it lines up with a raster in the same CRS.
    Results of tools (contours ...) are already in their raster's system and are left alone."""
    layer = layer_store.get(layer_id)
    if layer.geojson is None:
        raise BadRequest("This layer has no vector data.", code="not_a_vector")
    if not crs or layer.tool is not None:
        return layer.geojson
    return _reproject(layer.geojson, "EPSG:4326", crs)


def _vector(layer_id: str) -> Layer:
    layer = layer_store.get(layer_id)
    if layer.geojson is None:
        raise BadRequest("This layer has no vector data.", code="not_a_vector")
    return layer


def _field_names(features: list[dict]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for f in features:
        for k in (f.get("properties") or {}):
            if k not in seen:
                seen.add(k)
                names.append(k)
    return names


def _sort_key(value):
    # numbers sort as numbers, everything else as text; numbers come first
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value), "")
    return (1, 0.0, str(value))


def layer_attributes(layer_id: str, offset: int = 0, limit: int = 500, sort: str | None = None,
                     descending: bool = False, fields: list[str] | None = None) -> dict:
    """The attribute table of a vector layer: one page of rows, optionally sorted by a field.
    Each row is {"fid": feature number, "values": {field: value}}."""
    feats = _vector(layer_id).geojson.get("features", [])
    names = _field_names(feats)
    if sort is not None and sort not in names:
        raise BadRequest(f"Unknown field '{sort}'.", code="unknown_field")
    keep = names if not fields else [n for n in fields if n in names]
    order = list(range(len(feats)))
    if sort is not None:
        has = [i for i in order if (feats[i].get("properties") or {}).get(sort) is not None]
        none = [i for i in order if (feats[i].get("properties") or {}).get(sort) is None]
        has.sort(key=lambda i: _sort_key(feats[i]["properties"][sort]), reverse=descending)
        order = has + none
    rows = [{"fid": i, "values": {k: (feats[i].get("properties") or {}).get(k) for k in keep}}
            for i in order[offset:offset + limit]]
    return {"fields": names, "total": len(feats), "offset": offset, "rows": rows}


def identify(layer_id: str, x: float, y: float, tolerance: float, crs: str | None) -> dict:
    """The top-most feature at a point. (x, y) is in `crs` (default lon/lat) and `tolerance`
    is how close counts as a hit, in that system's units (metres for a projected system)."""
    layer = _vector(layer_id)
    src = (crs or "EPSG:4326").upper()
    tol = tolerance
    if src != "EPSG:4326":
        require_rasterio()
        from rasterio.warp import transform
        try:
            xs, ys = transform(src, "EPSG:4326", [x], [y])
        except Exception as exc:
            raise BadRequest(f"Could not use coordinate system {crs}: {exc}", code="bad_crs") from exc
        x, y = xs[0], ys[0]
        tol = tolerance / 111_320.0                      # metres -> degrees, good enough for a click
    fid = top_feature_at(layer.geojson.get("features", []), x, y, tol)
    if fid is None:
        return {"hit": False, "fid": None, "properties": {}}
    return {"hit": True, "fid": fid, "properties": layer.geojson["features"][fid].get("properties") or {}}


def vector_shapes(layer_id: str, raster: str | None, width: int | None, height: int | None,
                  fit_width: int = 768, fit_height: int = 512) -> dict:
    """Shapes of a vector layer in drawing cells. With `raster` (and the size `width` x `height`
    of the picture the window shows for it) they are lined up with that raster; without it the
    data is fitted into a fit_width x fit_height window."""
    layer = _vector(layer_id)
    if raster is None:
        return to_cells(layer.geojson, bounds=None, width=fit_width, height=fit_height)
    if not width or not height:
        raise BadRequest("width and height of the raster picture are needed with 'raster'.",
                         code="missing_size")
    r = get_raster_layer(raster).raster
    data = layer.geojson if layer.tool is not None else _reproject(layer.geojson, "EPSG:4326", r.crs)
    return to_cells(data, bounds=tuple(r.bounds), width=width, height=height)


# colour ramp a result of each tool is drawn with (everything else uses "terrain")
TOOL_RAMPS = {"hillshade": "greys", "slope": "slope", "aspect": "viridis", "curvature": "diverging"}


def layer_display(layer_id: str, bins: int = 30) -> dict:
    """What a window needs to draw a raster layer: the ramp to use, its statistics and histogram."""
    layer = layer_store.get(layer_id)
    out: dict = {"id": layer.id, "kind": layer.kind}
    if layer.raster is not None:
        out["ramp"] = TOOL_RAMPS.get(layer.tool or "", "terrain")
        out["statistics"] = {"layer": layer.name, **layer_stats.compute(layer.raster.data)}
        out["histogram"] = histogram.compute(layer.raster.data, bins)
    return out


def _reproject(data: dict, src: str, dst: str) -> dict:
    if src.upper() == dst.upper():
        return data
    rasterio = require_rasterio()
    from rasterio.warp import transform_geom
    feats = []
    for f in data.get("features", []):
        g = f.get("geometry")
        if g:
            try:
                g = transform_geom(src, dst, g)
            except Exception as exc:
                raise BadRequest(f"Could not convert the layer to {dst}: {exc}",
                                 code="bad_crs") from exc
        feats.append({**f, "geometry": g})
    return {**data, "features": feats}


# ---- export ----
def map_image(layer_id: str, ramp: str, vmin: float | None, vmax: float | None,
              max_pixels: int | None) -> bytes:
    raster = get_raster_layer(layer_id).raster
    limit = min(max_pixels or get_settings().max_png_pixels, get_settings().max_png_pixels)
    return render_png(raster, ramp, vmin, vmax, limit)


def export_elevations(layer_id: str, path: str) -> dict:
    raster = get_raster_layer(layer_id).raster
    return {"path": write_geotiff(raster, path)}


def statistics(layer_id: str, fmt: str):
    layer = get_raster_layer(layer_id)
    stats = {"layer": layer.name, **layer_stats.compute(layer.raster.data)}
    if fmt == "json":
        return stats
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(stats.keys())
    w.writerow(stats.values())
    return buf.getvalue()


# ---- workspace ----
def reset_workspace() -> dict:
    project.reset_workspace()
    return project.workspace


def set_fullscreen(enabled: bool) -> dict:
    project.workspace["fullscreen"] = enabled
    return {"fullscreen": enabled}


def exit_info() -> dict:
    return {"ok": True, "unsaved_changes": project.is_dirty(), "project": project.name}


def pixel_value(layer_id: str, row: int, col: int) -> dict:
    raster = get_raster_layer(layer_id).raster
    if row < 0 or col < 0 or row >= raster.height or col >= raster.width:
        raise BadRequest("Pixel row or column is outside the raster.", code="pixel_out_of_bounds")
    value = float(raster.data[row, col])
    x, y = raster.rowcol_to_xy(row, col)
    coordinate_unit = "map units"
    x_label, y_label = "Easting", "Northing"
    if raster.crs:
        rasterio = require_rasterio()
        crs = rasterio.crs.CRS.from_string(raster.crs)
        if crs.is_geographic:
            coordinate_unit = "°"
            x_label, y_label = "Longitude", "Latitude"
        else:
            axis = getattr(crs, "axis_info", None)  # not in older rasterio
            coordinate_unit = axis[0].unit_name if axis else getattr(crs, "linear_units", coordinate_unit)
    return {
        "row": row,
        "col": col,
        "value": value if math.isfinite(value) else None,
        "x": float(x),
        "y": float(y),
        "crs": raster.crs,
        "coordinate_unit": coordinate_unit,
        "x_label": x_label,
        "y_label": y_label,
    }


# ---- workspace ----
def reset_workspace() -> dict:
    project.reset_workspace()
    return project.workspace


def set_fullscreen(enabled: bool) -> dict:
    project.workspace["fullscreen"] = enabled
    return {"fullscreen": enabled}


def exit_info() -> dict:
    return {"ok": True, "unsaved_changes": project.is_dirty(), "project": project.name}
