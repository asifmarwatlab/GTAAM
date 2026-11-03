"""Curvature (Zevenbergen & Thorne). Positive = convex (hilltops), negative = concave."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def compute_curvature(dem: np.ndarray, dx: float, dy: float) -> np.ndarray:
    n = shifted(dem.astype(np.float64))
    d2x = ((n["w"] + n["e"]) / 2 - n["c"]) / dx ** 2
    d2y = ((n["n"] + n["s"]) / 2 - n["c"]) / dy ** 2
    return (-2.0 * (d2x + d2y) * 100.0).astype(np.float32)
