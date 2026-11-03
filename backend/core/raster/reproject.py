"""Move a raster to another coordinate system (needs rasterio)."""
from __future__ import annotations

import numpy as np

from ._deps import require_rasterio
from .model import Raster

METHODS = ("nearest", "bilinear", "cubic")


def reproject(raster: Raster, epsg: int, method: str = "bilinear") -> Raster:
    require_rasterio()
    from rasterio.transform import Affine
    from rasterio.warp import Resampling, calculate_default_transform
    from rasterio.warp import reproject as warp

    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    if not raster.crs:
        raise ValueError("This raster has no coordinate system, so it cannot be reprojected.")
    dst_crs = f"EPSG:{epsg}"
    t, w, h = calculate_default_transform(raster.crs, dst_crs, raster.width, raster.height,
                                          *raster.bounds)
    dst = np.full((h, w), np.nan, dtype=np.float32)
    warp(source=raster.data, destination=dst, src_transform=Affine(*raster.transform),
         src_crs=raster.crs, dst_transform=t, dst_crs=dst_crs,
         resampling=Resampling[method], src_nodata=np.nan, dst_nodata=np.nan)
    return Raster(dst, (t.a, t.b, t.c, t.d, t.e, t.f), dst_crs, raster.nodata)
