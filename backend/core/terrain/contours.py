"""Contour lines as GeoJSON (uses contourpy)."""
from __future__ import annotations

import math

import numpy as np

from core.raster.model import Raster

MAX_LEVELS = 500


def contour_lines(raster: Raster, interval: float, base: float = 0.0) -> dict:
    from contourpy import contour_generator

    if interval <= 0:
        raise ValueError("interval must be positive.")
    finite = raster.data[np.isfinite(raster.data)]
    if finite.size == 0:
        raise ValueError("The raster has no valid cells.")
    zmin, zmax = float(finite.min()), float(finite.max())
    first = base + math.ceil((zmin - base) / interval) * interval
    levels = np.arange(first, zmax + 1e-9, interval)
    if len(levels) > MAX_LEVELS:
        raise ValueError(f"That interval gives {len(levels)} contour levels; use a larger interval.")
    gen = contour_generator(x=raster.x_coords(), y=raster.y_coords(),
                            z=np.ma.masked_invalid(raster.data))
    features = []
    for level in levels:
        lines = [ln.tolist() for ln in gen.lines(float(level)) if len(ln) >= 2]
        if lines:
            features.append({"type": "Feature", "properties": {"elevation": float(level)},
                             "geometry": {"type": "MultiLineString", "coordinates": lines}})
    return {"type": "FeatureCollection", "features": features}
