from pydantic import BaseModel, Field

from schemas.common import XY


class LayerRequest(BaseModel):
    layer_id: str = Field(min_length=1)


class RegionCreate(LayerRequest):
    polygon: list[XY] = Field(min_length=3)       # in the layer's coordinate system
    name: str | None = None


class RegionSelect(LayerRequest):
    region_ids: list[str]


class _Edit(LayerRequest):
    region_ids: list[str] | None = None            # omit = use the currently selected regions


class RaiseLowerRequest(_Edit):
    amount: float = Field(description="Metres. Positive raises, negative lowers.")


class SmoothRequest(_Edit):
    iterations: int = Field(1, ge=1, le=100)


class FlattenRequest(_Edit):
    elevation: float | None = None                 # omit = the area's mean elevation


class FillSinksRequest(_Edit):
    pass


class ExportEditedRequest(LayerRequest):
    path: str = Field(min_length=1)
