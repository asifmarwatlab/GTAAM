"""Turn a drawn polygon into a True/False mask over the raster."""
from __future__ import annotations

import math

import numpy as np


def polygon_mask(shape: tuple[int, int], transform, polygon) -> np.ndarray:
    """True for every cell whose centre is inside the polygon (even-odd rule).

    polygon is a list of (x, y) in the raster's coordinate system.
    """
    poly = np.asarray(polygon, float)
    if poly.ndim != 2 or len(poly) < 3:
        raise ValueError("A region needs at least three points.")
    a, _, c, _, e, f = transform
    h, w = shape
    mask = np.zeros(shape, dtype=bool)
    cols = (poly[:, 0] - c) / a
    rows = (poly[:, 1] - f) / e
    c0, c1 = max(int(math.floor(cols.min())) - 1, 0), min(int(math.ceil(cols.max())) + 1, w)
    r0, r1 = max(int(math.floor(rows.min())) - 1, 0), min(int(math.ceil(rows.max())) + 1, h)
    if c0 >= c1 or r0 >= r1:
        return mask
    xs = c + (np.arange(c0, c1) + 0.5) * a
    ys = f + (np.arange(r0, r1) + 0.5) * e
    X, Y = np.meshgrid(xs, ys)
    inside = np.zeros(X.shape, dtype=bool)
    x1, y1 = poly[:, 0], poly[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    for xa, ya, xb, yb in zip(x1, y1, x2, y2):
        if ya == yb:
            continue
        crosses = (ya > Y) != (yb > Y)
        x_at = (xb - xa) * (Y - ya) / (yb - ya) + xa
        inside ^= crosses & (X < x_at)
    mask[r0:r1, c0:c1] = inside
    return mask
