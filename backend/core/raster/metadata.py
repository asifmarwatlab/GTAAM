"""Raster properties (the right-hand panel) and file metadata (Tools > Metadata)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._deps import require_rasterio
from .crs import epsg_code, is_geographic
from .model import Raster


def raster_properties(raster: Raster) -> dict:
    return {
        "coordinate_system": "Geographic" if is_geographic(raster) else "Projected",
        "crs": raster.crs,
        "epsg": epsg_code(raster),
        "pixel_size": [raster.pixel_w, raster.pixel_h],
        "dimensions": [raster.width, raster.height],
        "nodata_pixels": int(np.isnan(raster.data).sum()),
        "nodata_value": raster.nodata,
        "bands": 1,
        "bounds": list(raster.bounds),
    }


def file_metadata(path: str | Path) -> dict:
    rasterio = require_rasterio()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    with rasterio.open(p) as src:
        return {
            "file": str(p), "size_bytes": p.stat().st_size, "driver": src.driver,
            "dtype": src.dtypes[0], "bands": src.count, "width": src.width,
            "height": src.height, "crs": src.crs.to_string() if src.crs else None,
            "nodata": src.nodata, "tags": src.tags(),
        }
