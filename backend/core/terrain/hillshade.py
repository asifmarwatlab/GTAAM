"""Hillshade: how bright each cell looks with the sun at a given direction and height."""
from __future__ import annotations

import numpy as np

from .slope import gradients


def compute_hillshade(dem: np.ndarray, dx: float, dy: float, azimuth: float = 315.0,
                      altitude: float = 45.0, z_factor: float = 1.0) -> np.ndarray:
    gx, gn = gradients(dem, dx, dy)
    slope = np.arctan(z_factor * np.hypot(gx, gn))
    aspect = np.arctan2(-gx, -gn)                        # compass bearing of downhill, radians
    zenith = np.radians(90.0 - altitude)
    az = np.radians(azimuth)
    shade = np.cos(zenith) * np.cos(slope) + np.sin(zenith) * np.sin(slope) * np.cos(az - aspect)
    return (np.clip(shade, 0.0, 1.0) * 255.0).astype(np.float32)
