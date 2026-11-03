from typing import Literal

from pydantic import BaseModel, Field

from schemas.common import BBox


class LayerRequest(BaseModel):
    layer_id: str = Field(min_length=1)


class ClipRequest(LayerRequest):
    bounds: BBox


class ResampleRequest(LayerRequest):
    cell_size: float = Field(gt=0)               # in the layer's own units
    method: Literal["nearest", "bilinear"] = "bilinear"


class ReprojectRequest(LayerRequest):
    epsg: int = Field(gt=0)
    method: Literal["nearest", "bilinear", "cubic"] = "bilinear"


class FillNoDataRequest(LayerRequest):
    max_iterations: int = Field(50, ge=1, le=1000)


class IdentifyRequest(LayerRequest):
    x: float
    y: float


class OptionsUpdate(BaseModel):
    units: Literal["metric", "imperial"] | None = None
    decimals: int | None = Field(None, ge=0, le=8)
    default_ramp: str | None = None
