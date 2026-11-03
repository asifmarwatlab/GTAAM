from pydantic import BaseModel, Field


class IdentifyRequest(BaseModel):
    x: float
    y: float
    tolerance: float = Field(gt=0, description="how close counts as a hit, in the units of `crs`")
    crs: str | None = Field("EPSG:4326", description="coordinate system of x, y")


class ProjectNew(BaseModel):
    name: str = Field("Untitled project", min_length=1, max_length=120)


class ProjectPath(BaseModel):
    path: str = Field(min_length=1)


class ProjectSave(BaseModel):
    path: str | None = None           # omit to save over the current file
    name: str | None = None           # project name (Save As: usually the file name)
    gui: dict | None = None           # the window's own state, stored in the project


class ProjectSaveAs(ProjectPath):
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
