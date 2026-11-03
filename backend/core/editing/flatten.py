"""Flatten the terrain inside a mask to one elevation (default: the area's mean)."""
from __future__ import annotations

import numpy as np


def flatten(data: np.ndarray, mask: np.ndarray, elevation: float | None = None) -> np.ndarray:
    out = data.copy()
    target = mask & np.isfinite(data)
    if not target.any():
        return out
    level = float(np.mean(data[target])) if elevation is None else float(elevation)
    out[target] = level
    return out
