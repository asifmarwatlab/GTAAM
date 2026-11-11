from pydantic import BaseModel, Field, field_validator, model_validator


class IdentifyRequest(BaseModel):
    x: float
    y: float
    tolerance: float = Field(gt=0, description="how close counts as a hit, in the units of `crs`")
    crs: str | None = Field("EPSG:4326", description="coordinate system of x, y")


class ProjectNew(BaseModel):
    name: str = Field("Untitled project", min_length=1, max_length=120)


class ProjectPath(BaseModel):
    path: str = Field(min_length=1)


class CanvasLayer(BaseModel):
    """One layer as one map canvas shows it."""
    id: str = Field(min_length=1)
    visible: bool = True
    opacity: float = Field(1.0, ge=0.0, le=1.0)


class Canvas(BaseModel):
    """A map canvas: its own list of layers (top first), view and drawn regions.
    The layer data itself is shared - a layer can be in several canvases."""
    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    view: dict | None = None          # zoom and pan, kept for the window
    regions: list | None = None       # editing regions drawn on this canvas
    layers: list[CanvasLayer] = []

    @field_validator("layers")
    @classmethod
    def _no_duplicate_layers(cls, v: list[CanvasLayer]) -> list[CanvasLayer]:
        ids = [l.id for l in v]
        if len(ids) != len(set(ids)):
            raise ValueError("a layer can appear only once in a canvas")
        return v


class CanvasSet(BaseModel):
    canvases: list[Canvas] | None = None     # omit to keep the canvases the project already has
    active_canvas: str | None = None

    @model_validator(mode="after")
    def _check_canvases(self):
        if self.canvases is None:
            return self
        ids = [c.id for c in self.canvases]
        if len(ids) != len(set(ids)):
            raise ValueError("canvas ids must be unique")
        if self.active_canvas is not None and self.active_canvas not in ids:
            raise ValueError("active_canvas must be one of the canvases")
        return self


class ProjectSave(CanvasSet):
    path: str | None = None           # omit to save over the current file
    name: str | None = None           # project name (Save As: usually the file name)
    gui: dict | None = None           # the window's own state, stored in the project


class ProjectSaveAs(ProjectPath, CanvasSet):
    name: str | None = None
    gui: dict | None = None


class ProjectInfo(BaseModel):
    name: str
    path: str | None = None
    dirty: bool
    layer_count: int
    created: str


class SaveResult(ProjectInfo):
    saved_layers: int
    skipped_layers: list[str] = []    # layers that could not be written to disk


class OpenResult(ProjectInfo):
    missing_layers: list[str] = []
    gui: dict = {}                    # window state saved with the project
    canvases: list[Canvas] = []       # the map canvases (always at least one)
    active_canvas: str | None = None
    layers: list[dict] = []           # every layer, top first (rasters carry a "display" bundle)


class AddRasterRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None


class AddVectorRequest(BaseModel):
    path: str = Field(min_length=1)   # a GeoJSON file
    name: str | None = None


class AddBasemapRequest(BaseModel):
    name: str = Field(min_length=1)
    url_template: str = Field(min_length=1)   # e.g. https://tile.openstreetmap.org/{z}/{x}/{y}.png
    attribution: str | None = None


class LayerUpdate(BaseModel):
    name: str | None = None
    visible: bool | None = None
    opacity: float | None = Field(None, ge=0, le=1)


class LayerOrder(BaseModel):
    layer_ids: list[str]              # top of the drawing order first


class ExportElevationsRequest(BaseModel):
    layer_id: str
    path: str = Field(min_length=1)


class FullscreenRequest(BaseModel):
    enabled: bool
