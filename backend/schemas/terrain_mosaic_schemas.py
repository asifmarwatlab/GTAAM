from typing import Literal

from pydantic import BaseModel, Field


class SelectDems(BaseModel):
    layer_ids: list[str] = Field(min_length=2)


class PairRequest(BaseModel):
    layer_a: str | None = None        # omit both to use the first two selected DEMs
    layer_b: str | None = None


class BlendSettings(BaseModel):
    method: Literal["feather", "first", "last", "mean", "min", "max"] = "feather"
    feather_pixels: int = Field(20, ge=0, le=500)


class ExportMosaicRequest(BaseModel):
    path: str = Field(min_length=1)
