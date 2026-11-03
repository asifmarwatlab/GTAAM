"""Terrain Ruggedness Index (Riley et al. 1999)."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def compute_ruggedness(dem: np.ndarray) -> np.ndarray:
    n = shifted(dem.astype(np.float64))
    sq = sum((v - n["c"]) ** 2 for k, v in n.items() if k != "c")
    return np.sqrt(sq).astype(np.float32)
