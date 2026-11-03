"""Merge several DEMs into one."""
from __future__ import annotations

import numpy as np

from core.raster.model import Raster

from .blend import edge_weight
from .grid import check_compatible, place, union_bounds

METHODS = ("feather", "first", "last", "mean", "min", "max")


def mosaic(rasters: list[Raster], method: str = "feather", feather_pixels: int = 20) -> Raster:
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if len(rasters) < 2:
        raise ValueError("Select at least two DEMs.")
    check_compatible(rasters)
    first = rasters[0]
    minx, miny, maxx, maxy = union_bounds(rasters)
    shape = (int(round((maxy - miny) / first.pixel_h)), int(round((maxx - minx) / first.pixel_w)))
    layers = np.stack([place(r, minx, maxy, shape) for r in rasters]).astype(np.float64)
    valid = np.isfinite(layers)

    if method == "feather":
        weights = np.stack([edge_weight(v, feather_pixels) for v in valid]).astype(np.float64)
        total = weights.sum(axis=0)
        out = np.where(total > 0, (np.where(valid, layers, 0) * weights).sum(axis=0) / np.maximum(total, 1e-12), np.nan)
    elif method in ("first", "last"):
        out = np.full(shape, np.nan)
        order = range(len(rasters) - 1, -1, -1) if method == "first" else range(len(rasters))
        for i in order:                           # later writes win, so reverse for "first"
            out = np.where(valid[i], layers[i], out)
    else:
        with np.errstate(all="ignore"):
            out = {"mean": np.nanmean, "min": np.nanmin, "max": np.nanmax}[method](layers, axis=0)
    transform = (first.pixel_w, 0.0, minx, 0.0, -first.pixel_h, maxy)
    return Raster(out.astype(np.float32), transform, first.crs, first.nodata)
