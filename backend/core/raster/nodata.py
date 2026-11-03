"""NoData handling: find it, count it, fill it."""
from __future__ import annotations

import numpy as np

from .windows import shifted


def nodata_mask(data: np.ndarray) -> np.ndarray:
    return ~np.isfinite(data)


def fill_nodata(data: np.ndarray, max_iterations: int = 50) -> np.ndarray:
    """Fill holes from the edge inwards with the mean of their valid neighbours.

    Each pass fills the NoData cells that touch valid data, so a hole N cells wide
    needs about N/2 passes.
    """
    out = data.astype(np.float32, copy=True)
    for _ in range(max_iterations):
        holes = ~np.isfinite(out)
        if not holes.any():
            break
        stack = np.stack([v for k, v in shifted(out).items() if k != "c"])
        valid = np.isfinite(stack)
        counts = valid.sum(axis=0)
        sums = np.where(valid, stack, 0.0).sum(axis=0)
        fillable = holes & (counts > 0)
        if not fillable.any():
            break                                  # whole raster is NoData
        out[fillable] = sums[fillable] / counts[fillable]
    return out
