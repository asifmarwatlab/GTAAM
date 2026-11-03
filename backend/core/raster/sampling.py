"""Read raster values at arbitrary coordinates."""
from __future__ import annotations

import numpy as np

from .model import Raster


def sample_nearest(raster: Raster, xs, ys) -> np.ndarray:
    xs, ys = np.atleast_1d(np.asarray(xs, float)), np.atleast_1d(np.asarray(ys, float))
    row, col = raster.xy_to_rowcol(xs, ys)
    inside = (row >= 0) & (row < raster.height) & (col >= 0) & (col < raster.width)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    out[inside] = raster.data[row[inside], col[inside]]
    return out


def sample_bilinear(raster: Raster, xs, ys) -> np.ndarray:
    xs, ys = np.atleast_1d(np.asarray(xs, float)), np.atleast_1d(np.asarray(ys, float))
    # continuous pixel coordinates where pixel centres sit on whole numbers
    fc = (xs - raster.origin_x) / raster.pixel_w - 0.5
    fr = (raster.origin_y - ys) / raster.pixel_h - 0.5
    r0, c0 = np.floor(fr).astype(int), np.floor(fc).astype(int)
    tr, tc = fr - r0, fc - c0
    inside = (r0 >= 0) & (r0 < raster.height - 1) & (c0 >= 0) & (c0 < raster.width - 1)
    out = np.full(xs.shape, np.nan, dtype=np.float64)
    r, c = r0[inside], c0[inside]
    d = raster.data
    top = d[r, c] * (1 - tc[inside]) + d[r, c + 1] * tc[inside]
    bot = d[r + 1, c] * (1 - tc[inside]) + d[r + 1, c + 1] * tc[inside]
    out[inside] = top * (1 - tr[inside]) + bot * tr[inside]
    return out
