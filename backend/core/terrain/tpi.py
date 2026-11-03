"""Topographic Position Index = cell elevation minus the mean of its 8 neighbours."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def compute_tpi(dem: np.ndarray) -> np.ndarray:
    n = shifted(dem.astype(np.float64))
    ring = np.stack([v for k, v in n.items() if k != "c"]).mean(axis=0)
    return (n["c"] - ring).astype(np.float32)
