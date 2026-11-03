"""The one data type every core function understands: a single-band, north-up raster.

data      2-D float32 array, NaN wherever there is no data
transform (a, b, c, d, e, f) as in rasterio/GDAL: a = pixel width, e = -pixel height,
          (c, f) = top-left corner. Rotated rasters are not supported.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

Transform = tuple[float, float, float, float, float, float]


@dataclass
class Raster:
    data: np.ndarray
    transform: Transform
    crs: str | None = None
    nodata: float | None = None

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError("Raster data must be a 2-D array (one band).")
        if self.transform[1] != 0 or self.transform[3] != 0:
            raise ValueError("Rotated rasters are not supported.")
        if self.transform[4] >= 0 or self.transform[0] <= 0:
            raise ValueError("Only north-up rasters are supported.")
        if self.data.dtype != np.float32:
            self.data = self.data.astype(np.float32)

    # ---- geometry ----
    @property
    def height(self) -> int:
        return int(self.data.shape[0])

    @property
    def width(self) -> int:
        return int(self.data.shape[1])

    @property
    def pixel_w(self) -> float:
        return float(self.transform[0])

    @property
    def pixel_h(self) -> float:
        return float(-self.transform[4])

    @property
    def origin_x(self) -> float:
        return float(self.transform[2])

    @property
    def origin_y(self) -> float:
        return float(self.transform[5])

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y)"""
        return (self.origin_x, self.origin_y - self.height * self.pixel_h,
                self.origin_x + self.width * self.pixel_w, self.origin_y)

    def x_coords(self) -> np.ndarray:
        return self.origin_x + (np.arange(self.width) + 0.5) * self.pixel_w

    def y_coords(self) -> np.ndarray:
        return self.origin_y - (np.arange(self.height) + 0.5) * self.pixel_h

    def xy_to_rowcol(self, x, y):
        """Row/col of the pixel that contains (x, y). Works on numbers or arrays."""
        col = np.floor((np.asarray(x, float) - self.origin_x) / self.pixel_w).astype(int)
        row = np.floor((self.origin_y - np.asarray(y, float)) / self.pixel_h).astype(int)
        return row, col

    def rowcol_to_xy(self, row, col):
        """Coordinates of the pixel centre."""
        x = self.origin_x + (np.asarray(col, float) + 0.5) * self.pixel_w
        y = self.origin_y - (np.asarray(row, float) + 0.5) * self.pixel_h
        return x, y

    # ---- helpers ----
    def with_data(self, data: np.ndarray) -> "Raster":
        return replace(self, data=data)

    def copy(self) -> "Raster":
        return replace(self, data=self.data.copy())

    def summary(self) -> dict:
        return {"width": self.width, "height": self.height, "bounds": self.bounds,
                "crs": self.crs, "pixel_size": (self.pixel_w, self.pixel_h),
                "nodata": self.nodata}
