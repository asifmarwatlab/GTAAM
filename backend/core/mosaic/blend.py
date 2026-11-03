"""Feather weights: 0+ at a raster's edge, rising to 1 a few pixels inside."""
from __future__ import annotations

import numpy as np


def edge_weight(valid: np.ndarray, feather_pixels: int) -> np.ndarray:
    weight = np.zeros(valid.shape, dtype=np.float32)
    if feather_pixels < 1:
        weight[valid] = 1.0
        return weight
    current = valid.copy()
    for k in range(1, feather_pixels + 1):
        weight[current] = k / feather_pixels
        p = np.pad(current, 1, constant_values=False)
        current = current & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        if not current.any():
            return weight
    weight[current] = 1.0
    return weight
