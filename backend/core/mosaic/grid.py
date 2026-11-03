"""Place rasters that share the same pixel size onto a common grid."""
from __future__ import annotations

import numpy as np

from core.raster.model import Raster


def check_compatible(rasters: list[Raster], rel_tol: float = 1e-6) -> None:
    first = rasters[0]
    for r in rasters[1:]:
        if (r.crs or None) != (first.crs or None):
            raise ValueError("The DEMs use different coordinate systems. Reproject them first.")
        if (abs(r.pixel_w - first.pixel_w) > rel_tol * first.pixel_w
                or abs(r.pixel_h - first.pixel_h) > rel_tol * first.pixel_h):
            raise ValueError("The DEMs have different cell sizes. Resample them first.")


def union_bounds(rasters: list[Raster]) -> tuple[float, float, float, float]:
    b = np.array([r.bounds for r in rasters])
    return (b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max())


def overlap_bounds(a: Raster, b: Raster):
    minx, miny = max(a.bounds[0], b.bounds[0]), max(a.bounds[1], b.bounds[1])
    maxx, maxy = min(a.bounds[2], b.bounds[2]), min(a.bounds[3], b.bounds[3])
    if minx >= maxx or miny >= maxy:
        return None
    return minx, miny, maxx, maxy


def window(raster: Raster, bounds) -> np.ndarray:
    """The part of raster.data covered by bounds (bounds must lie inside the raster)."""
    minx, miny, maxx, maxy = bounds
    c0 = int(round((minx - raster.origin_x) / raster.pixel_w))
    r0 = int(round((raster.origin_y - maxy) / raster.pixel_h))
    c1 = c0 + int(round((maxx - minx) / raster.pixel_w))
    r1 = r0 + int(round((maxy - miny) / raster.pixel_h))
    return raster.data[max(r0, 0):r1, max(c0, 0):c1]


def place(raster: Raster, origin_x: float, origin_y: float, shape: tuple[int, int]) -> np.ndarray:
    """raster.data pasted into an all-NaN array of `shape` whose top-left is the origin."""
    out = np.full(shape, np.nan, dtype=np.float32)
    c0 = int(round((raster.origin_x - origin_x) / raster.pixel_w))
    r0 = int(round((origin_y - raster.origin_y) / raster.pixel_h))
    out[r0:r0 + raster.height, c0:c0 + raster.width] = raster.data
    return out
