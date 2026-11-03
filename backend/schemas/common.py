"""Shapes used by more than one module. Module-specific shapes stay in that module."""
from typing import Any

from pydantic import BaseModel, Field, model_validator

XY = tuple[float, float]          # (x, y) in the layer's coordinate system


class BBox(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @model_validator(mode="after")
    def _ordered(self):
        if self.min_x >= self.max_x or self.min_y >= self.max_y:
            raise ValueError("BBox needs min_x < max_x and min_y < max_y")
        return self

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.min_x, self.min_y, self.max_x, self.max_y)


class LayerRef(BaseModel):
    layer_id: str = Field(min_length=1)


class LayerInfo(BaseModel):
    id: str
    name: str
    kind: str                          # raster | vector | basemap
    source: str | None = None
    visible: bool = True
    opacity: float = 1.0
    derived_from: str | None = None
    tool: str | None = None
    meta: dict[str, Any] = {}
    # raster-only
    width: int | None = None
    height: int | None = None
    bounds: tuple[float, float, float, float] | None = None
    crs: str | None = None
    pixel_size: tuple[float, float] | None = None
    nodata: float | None = None


class DerivedLayerResult(BaseModel):
    """What a tool returns when it creates a new layer."""
    layer: LayerInfo
    statistics: dict[str, Any] | None = None
    extra: dict[str, Any] = {}


class Message(BaseModel):
    ok: bool = True
    message: str = ""
