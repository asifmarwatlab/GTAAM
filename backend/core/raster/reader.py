"""Open a DEM file (GeoTIFF etc.) as a Raster."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._deps import require_rasterio
from .model import Raster


def read_raster(path: str | Path, band: int = 1) -> Raster:
    rasterio = require_rasterio()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Raster file not found: {path}")
    with rasterio.open(p) as src:
        if not 1 <= band <= src.count:
            raise ValueError(f"Band {band} does not exist (file has {src.count}).")
        masked = src.read(band, masked=True)
        data = np.ma.filled(masked.astype("float32"), np.nan)
        t = src.transform
        crs = src.crs.to_string() if src.crs else None
        return Raster(data=data, transform=(t.a, t.b, t.c, t.d, t.e, t.f), crs=crs,
                      nodata=src.nodata)
