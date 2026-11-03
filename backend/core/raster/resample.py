"""Change a raster's cell size."""
from __future__ import annotations

import numpy as np

from .model import Raster
from .sampling import sample_bilinear, sample_nearest

METHODS = ("nearest", "bilinear")


def resample(raster: Raster, cell_size: float, method: str = "bilinear") -> Raster:
    """cell_size is in the raster's own units (degrees for EPSG:4326, metres for UTM)."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if cell_size <= 0:
        raise ValueError("cell_size must be positive.")
    minx, miny, maxx, maxy = raster.bounds
    width = max(int(round((maxx - minx) / cell_size)), 1)
    height = max(int(round((maxy - miny) / cell_size)), 1)
    if width * height > 100_000_000:
        raise ValueError("That cell size would create a raster larger than 100 million cells.")
    xs = minx + (np.arange(width) + 0.5) * cell_size
    ys = maxy - (np.arange(height) + 0.5) * cell_size
    gx, gy = np.meshgrid(xs, ys)
    sampler = sample_bilinear if method == "bilinear" else sample_nearest
    data = sampler(raster, gx.ravel(), gy.ravel()).reshape(height, width).astype(np.float32)
    transform = (cell_size, 0.0, minx, 0.0, -cell_size, maxy)
    return Raster(data, transform, raster.crs, raster.nodata)
