"""Aspect: the compass direction the slope faces (0 = north, 90 = east, clockwise)."""
from __future__ import annotations

import numpy as np

from .slope import gradients


def compute_aspect(dem: np.ndarray, dx: float, dy: float,
                   flat_value: float | None = None) -> np.ndarray:
    gx, gn = gradients(dem, dx, dy)
    # downhill direction = -gradient; bearing measured clockwise from north
    aspect = (np.degrees(np.arctan2(-gx, -gn)) + 360.0) % 360.0
    # flat cells have no aspect: NaN by default, or a chosen value such as -1
    aspect[np.hypot(gx, gn) < 1e-12] = np.nan if flat_value is None else flat_value
    return aspect.astype(np.float32)
