"""Roughness = largest elevation difference inside each 3x3 window (GDAL definition)."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def compute_roughness(dem: np.ndarray) -> np.ndarray:
    stack = np.stack(list(shifted(dem).values()))
    return (stack.max(axis=0) - stack.min(axis=0)).astype(np.float32)
