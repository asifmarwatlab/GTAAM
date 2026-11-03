"""Analysis tab logic. Finds the layer, calls core/, packages the answer."""
from __future__ import annotations

from typing import Callable

import numpy as np

from core.measure import area as core_area
from core.measure import distance as core_distance
from core.measure import profile as core_profile
from core.raster.crs import cell_size_meters, is_geographic
from core.stats import histogram, layer_stats, nodata_check, outliers
from core.terrain.aspect import compute_aspect
from core.terrain.contours import contour_lines
from core.terrain.curvature import compute_curvature
from core.terrain.hillshade import compute_hillshade
from core.terrain.roughness import compute_roughness
from core.terrain.ruggedness import compute_ruggedness
from core.terrain.slope import compute_slope
from core.terrain.tpi import compute_tpi
from config import get_settings
from shared.errors import BadRequest
from shared.layer_store import Layer, add_raster_layer, add_vector_layer, get_raster_layer


def _layer(layer_id: str) -> Layer:
    return get_raster_layer(layer_id)


def _derive(src: Layer, data: np.ndarray, tool: str, label: str) -> dict:
    out = add_raster_layer(src.raster.with_data(data), f"{src.name} - {label}",
                           derived_from=src.id, tool=tool)
    return {"layer": out.info(), "statistics": layer_stats.compute(data)}


# ---- measure ----
def distance(layer_id: str, points) -> dict:
    r = _layer(layer_id).raster
    return core_distance.path_length(points, is_geographic(r))


def area(layer_id: str, polygon) -> dict:
    r = _layer(layer_id).raster
    return core_area.polygon_area(polygon, is_geographic(r))


def elevation_profile(layer_id: str, line, samples: int) -> dict:
    r = _layer(layer_id).raster
    return core_profile.elevation_profile(r, line, is_geographic(r), samples)


# ---- quality & statistics ----
def layer_statistics(layer_id: str) -> dict:
    return layer_stats.compute(_layer(layer_id).raster.data)


def get_histogram(layer_id: str, bins: int) -> dict:
    if not 1 <= bins <= get_settings().max_histogram_bins:
        raise BadRequest(f"bins must be between 1 and {get_settings().max_histogram_bins}.",
                         code="bad_bins")
    return histogram.compute(_layer(layer_id).raster.data, bins)


def nodata(layer_id: str) -> dict:
    return nodata_check.run(_layer(layer_id).raster.data)


def outlier_check(layer_id: str, method: str, threshold: float | None) -> dict:
    return outliers.run(_layer(layer_id).raster.data, method, threshold)


# ---- surface analysis & terrain derivatives (all create a new raster layer) ----
def _surface(layer_id: str, tool: str, label: str,
             fn: Callable[[np.ndarray, float, float], np.ndarray]) -> dict:
    src = _layer(layer_id)
    dx, dy = cell_size_meters(src.raster)
    return _derive(src, fn(src.raster.data, dx, dy), tool, label)


def hillshade(layer_id: str, azimuth: float, altitude: float, z_factor: float) -> dict:
    return _surface(layer_id, "hillshade", "hillshade",
                    lambda d, dx, dy: compute_hillshade(d, dx, dy, azimuth, altitude, z_factor))


def slope(layer_id: str, units: str) -> dict:
    return _surface(layer_id, "slope", f"slope ({units})",
                    lambda d, dx, dy: compute_slope(d, dx, dy, units))


def aspect(layer_id: str, flat_as_minus_one: bool = False) -> dict:
    flat_value = -1.0 if flat_as_minus_one else None
    return _surface(layer_id, "aspect", "aspect",
                    lambda d, dx, dy: compute_aspect(d, dx, dy, flat_value))


def curvature(layer_id: str) -> dict:
    return _surface(layer_id, "curvature", "curvature", compute_curvature)


def roughness(layer_id: str) -> dict:
    src = _layer(layer_id)
    return _derive(src, compute_roughness(src.raster.data), "roughness", "roughness")


def tpi(layer_id: str) -> dict:
    src = _layer(layer_id)
    return _derive(src, compute_tpi(src.raster.data), "tpi", "TPI")


def ruggedness(layer_id: str) -> dict:
    src = _layer(layer_id)
    return _derive(src, compute_ruggedness(src.raster.data), "ruggedness", "ruggedness (TRI)")


def contours(layer_id: str, interval: float, base: float) -> dict:
    src = _layer(layer_id)
    fc = contour_lines(src.raster, interval, base)
    out = add_vector_layer(fc, f"{src.name} - contours {interval:g}", derived_from=src.id,
                           tool="contours")
    return {"layer": out.info(), "statistics": None, "extra": {"feature_count": len(fc["features"])}}
