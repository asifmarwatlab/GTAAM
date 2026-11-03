"""Save a Raster as a GeoTIFF."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ._deps import require_rasterio
from .model import Raster

DEFAULT_NODATA = -9999.0


def write_geotiff(raster: Raster, path: str | Path) -> str:
    rasterio = require_rasterio()
    from rasterio.transform import Affine

    p = Path(path)
    if p.suffix.lower() not in (".tif", ".tiff"):
        p = p.with_suffix(".tif")
    p.parent.mkdir(parents=True, exist_ok=True)
    nodata = raster.nodata if raster.nodata is not None else DEFAULT_NODATA
    out = np.where(np.isfinite(raster.data), raster.data, nodata).astype("float32")
    with rasterio.open(
        p, "w", driver="GTiff", height=raster.height, width=raster.width, count=1,
        dtype="float32", crs=raster.crs, transform=Affine(*raster.transform), nodata=nodata,
        compress="deflate",
    ) as dst:
        dst.write(out, 1)
    return str(p)
