"""Slope using Horn's method (3x3 weighted gradient), same as GDAL/QGIS."""
from __future__ import annotations

import numpy as np

from core.raster.windows import shifted


def gradients(dem: np.ndarray, dx: float, dy: float) -> tuple[np.ndarray, np.ndarray]:
    """(gx, gn): rise per metre going east, and going north. dx, dy = cell size in metres."""
    n = shifted(dem.astype(np.float64))
    gx = ((n["ne"] + 2 * n["e"] + n["se"]) - (n["nw"] + 2 * n["w"] + n["sw"])) / (8 * dx)
    gn = ((n["nw"] + 2 * n["n"] + n["ne"]) - (n["sw"] + 2 * n["s"] + n["se"])) / (8 * dy)
    return gx, gn


def compute_slope(dem: np.ndarray, dx: float, dy: float, units: str = "degrees") -> np.ndarray:
    if units not in ("degrees", "percent"):
        raise ValueError("units must be 'degrees' or 'percent'")
    gx, gn = gradients(dem, dx, dy)
    rise = np.hypot(gx, gn)
    out = np.degrees(np.arctan(rise)) if units == "degrees" else rise * 100.0
    return out.astype(np.float32)
