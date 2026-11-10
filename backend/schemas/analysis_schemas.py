from typing import Literal

from pydantic import BaseModel, Field, model_validator

from schemas.common import XY


class LayerRequest(BaseModel):
    layer_id: str = Field(min_length=1)


class AspectRequest(LayerRequest):
    flat_as_minus_one: bool = False


class DistanceRequest(LayerRequest):
    points: list[XY] | None = Field(None, min_length=2)    # map coordinates (the layer's CRS)
    pixels: list[XY] | None = Field(None, min_length=2)    # clicked cells as (row, col)
    units: Literal["metres", "kilometres", "feet", "miles"] = "metres"
    include_elevation: bool = True
    snap: bool = False                  # move each click to the centre of its cell

    @model_validator(mode="after")
    def _one_kind_of_point(self):
        if (self.points is None) == (self.pixels is None):
            raise ValueError("Send either 'points' or 'pixels', not both and not neither.")
        return self


class AreaRequest(LayerRequest):
    polygon: list[XY] = Field(min_length=3)


class ProfileRequest(LayerRequest):
    line: list[XY] = Field(min_length=2)
    samples: int = Field(200, ge=2, le=5000)


class HillshadeRequest(LayerRequest):
    azimuth: float = Field(315, ge=0, le=360)
    altitude: float = Field(45, ge=0, le=90)
    z_factor: float = Field(1.0, gt=0)


class SlopeRequest(LayerRequest):
    units: Literal["degrees", "percent"] = "degrees"


class ContoursRequest(LayerRequest):
    interval: float = Field(100.0, gt=0)
    base: float = 0.0
