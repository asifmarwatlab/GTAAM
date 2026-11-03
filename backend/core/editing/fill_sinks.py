"""Fill sinks (pits) so water can flow out - Planchon & Darboux, vectorised.

Large basins can need many passes; max_iterations stops runaway work.
"""
from __future__ import annotations

import numpy as np


def fill_sinks(data: np.ndarray, mask: np.ndarray | None = None, max_iterations: int = 2000) -> np.ndarray:
    z = data.astype(np.float64)
    nodata = ~np.isfinite(z)
    z_work = np.where(nodata, -np.inf, z)               # NoData acts as an outlet
    w = np.full(z.shape, np.inf)
    w[0, :], w[-1, :], w[:, 0], w[:, -1] = z_work[0, :], z_work[-1, :], z_work[:, 0], z_work[:, -1]
    w[nodata] = -np.inf
    fixed = np.zeros(z.shape, dtype=bool)
    fixed[0, :] = fixed[-1, :] = fixed[:, 0] = fixed[:, -1] = True
    fixed |= nodata
    h, wd = z.shape
    for _ in range(max_iterations):
        p = np.pad(w, 1, mode="constant", constant_values=np.inf)
        neigh = np.min(np.stack([
            p[0:h, 0:wd], p[0:h, 1:wd + 1], p[0:h, 2:wd + 2], p[1:h + 1, 0:wd],
            p[1:h + 1, 2:wd + 2], p[2:h + 2, 0:wd], p[2:h + 2, 1:wd + 1], p[2:h + 2, 2:wd + 2],
        ]), axis=0)
        new_w = np.where(fixed, w, np.maximum(z_work, np.minimum(w, neigh)))
        if np.array_equal(new_w, w):
            break
        w = new_w
    filled = np.where(nodata, np.nan, w).astype(np.float32)
    if mask is not None:
        return np.where(mask, filled, data).astype(np.float32)
    return filled
