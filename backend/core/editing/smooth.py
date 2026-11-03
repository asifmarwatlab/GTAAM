"""Smooth the terrain inside a mask with a 3x3 mean filter."""
from __future__ import annotations

import numpy as np

from core.raster.windows import bbox_of_mask, shifted


def smooth(data: np.ndarray, mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    if iterations < 1:
        raise ValueError("iterations must be at least 1.")
    out = data.copy()
    box = bbox_of_mask(mask, pad=iterations + 1)
    if box is None:
        return out
    r0, r1, c0, c1 = box
    sub = out[r0:r1, c0:c1].copy()
    m = mask[r0:r1, c0:c1]
    for _ in range(iterations):
        stack = np.stack(list(shifted(sub).values()))
        valid = np.isfinite(stack)
        counts = valid.sum(axis=0)
        mean = np.where(counts > 0, np.where(valid, stack, 0.0).sum(axis=0) / np.maximum(counts, 1),
                        np.nan)
        sub = np.where(m & np.isfinite(sub), mean, sub).astype(np.float32)
    out[r0:r1, c0:c1] = sub
    return out
