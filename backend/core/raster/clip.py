"""Cut a raster to a bounding box."""
from __future__ import annotations

import math

from .model import Raster


def clip(raster: Raster, bounds: tuple[float, float, float, float]) -> Raster:
    minx, miny, maxx, maxy = bounds
    rminx, rminy, rmaxx, rmaxy = raster.bounds
    minx, miny, maxx, maxy = max(minx, rminx), max(miny, rminy), min(maxx, rmaxx), min(maxy, rmaxy)
    if minx >= maxx or miny >= maxy:
        raise ValueError("The clip box does not overlap the raster.")
    c0 = max(int(math.floor((minx - raster.origin_x) / raster.pixel_w)), 0)
    c1 = min(int(math.ceil((maxx - raster.origin_x) / raster.pixel_w)), raster.width)
    r0 = max(int(math.floor((raster.origin_y - maxy) / raster.pixel_h)), 0)
    r1 = min(int(math.ceil((raster.origin_y - miny) / raster.pixel_h)), raster.height)
    if r1 <= r0 or c1 <= c0:
        raise ValueError("The clip box is smaller than one pixel.")
    t = raster.transform
    new_t = (t[0], 0.0, raster.origin_x + c0 * raster.pixel_w, 0.0, t[4],
             raster.origin_y - r0 * raster.pixel_h)
    return Raster(raster.data[r0:r1, c0:c1].copy(), new_t, raster.crs, raster.nodata)
