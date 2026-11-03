from pydantic import BaseModel, Field

from schemas.common import XY


class ZoomRequest(BaseModel):
    factor: float = Field(2.0, gt=1.0, le=100)


class ViewportUpdate(BaseModel):
    center: XY | None = None
    scale: float | None = Field(None, gt=0)       # map scale denominator, e.g. 39236 for 1:39,236


class ModeRequest(BaseModel):
    mode: str = Field(pattern="^(explore|identify|measure|draw)$")


class PaneUpdate(BaseModel):
    visible: bool


class AppearanceUpdate(BaseModel):
    north_arrow: bool | None = None
    scale_bar: bool | None = None
    layer_label: bool | None = None
    colour_ramp: str | None = None


class DisplayToggles(BaseModel):
    regions: bool | None = None
    reference_grid: bool | None = None
    annotation: bool | None = None


class AnnotationCreate(BaseModel):
    x: float
    y: float
    text: str = Field(min_length=1, max_length=500)
