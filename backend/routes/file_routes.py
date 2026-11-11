"""File tab routes (/file).

Thin HTTP layer: read the request, call services/file_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from fastapi import Query, Response, status
from schemas.common import LayerInfo, Message
from schemas.file_schemas import AddBasemapRequest, AddRasterRequest, AddVectorRequest, ExportElevationsRequest, FullscreenRequest, IdentifyRequest, LayerOrder, LayerUpdate, OpenResult, ProjectInfo, ProjectNew, ProjectPath, ProjectSave, ProjectSaveAs, SaveResult
from typing import Literal
from services import file_service as service


# ======================================================================
# File · Project  (/file/project)
# ======================================================================
project_router = APIRouter(prefix="/project", tags=["File · Project"])


@project_router.get("", response_model=ProjectInfo)
def current_project():
    """Name, path and unsaved-changes flag of the open project."""
    return service.project_info()


@project_router.post("/new", response_model=ProjectInfo)
def new_project(req: ProjectNew):
    return service.new_project(req.name)


@project_router.post("/open", response_model=OpenResult)
def open_project(req: ProjectPath):
    return service.open_project(req.path)


def _canvases(req) -> list[dict] | None:
    return None if req is None or req.canvases is None else [c.model_dump() for c in req.canvases]


@project_router.post("/save", response_model=SaveResult)
def save_project(req: ProjectSave | None = None):
    return service.save_project(req.path if req else None, req.gui if req else None,
                                req.name if req else None, _canvases(req),
                                req.active_canvas if req else None)


@project_router.post("/save-as", response_model=SaveResult)
def save_project_as(req: ProjectSaveAs):
    return service.save_project(req.path, req.gui, req.name, _canvases(req), req.active_canvas)

# ======================================================================
# File · Add Data  (/file/add-data)
# ======================================================================
add_data_router = APIRouter(prefix="/add-data", tags=["File · Add Data"])


@add_data_router.post("/raster", response_model=LayerInfo, status_code=status.HTTP_201_CREATED)
def add_raster(req: AddRasterRequest):
    return service.add_raster(req.path, req.name)


@add_data_router.post("/vector", response_model=LayerInfo, status_code=status.HTTP_201_CREATED)
def add_vector(req: AddVectorRequest):
    return service.add_vector(req.path, req.name)


@add_data_router.post("/basemap", response_model=LayerInfo, status_code=status.HTTP_201_CREATED)
def add_basemap(req: AddBasemapRequest):
    return service.add_basemap(req.name, req.url_template, req.attribution)


@add_data_router.get("/layers", response_model=list[LayerInfo])
def list_layers():
    """Layers in drawing order, top first (feeds the Layers panel)."""
    return service.list_layers()


@add_data_router.put("/layers/order", response_model=list[LayerInfo])
def reorder_layers(req: LayerOrder):
    return service.reorder_layers(req.layer_ids)


@add_data_router.patch("/layers/{layer_id}", response_model=LayerInfo)
def update_layer(layer_id: str, req: LayerUpdate):
    return service.update_layer(layer_id, req.model_dump(exclude_none=True))


@add_data_router.delete("/layers/{layer_id}", response_model=Message)
def remove_layer(layer_id: str):
    service.remove_layer(layer_id)
    return Message(message="Layer removed.")


@add_data_router.get("/layers/{layer_id}/geojson")
def layer_geojson(layer_id: str, crs: str | None = Query(None, description="e.g. EPSG:32643")):
    return service.layer_geojson(layer_id, crs)


@add_data_router.get("/layers/{layer_id}/shapes")
def layer_shapes(layer_id: str, raster: str | None = None, width: int | None = Query(None, gt=0),
                 height: int | None = Query(None, gt=0), fit_width: int = Query(768, gt=0),
                 fit_height: int = Query(512, gt=0)):
    """Shapes of a vector layer as drawing cells (lined up with `raster`'s picture, or fitted)."""
    return service.vector_shapes(layer_id, raster, width, height, fit_width, fit_height)


@add_data_router.get("/layers/{layer_id}/attributes")
def layer_attributes(layer_id: str, offset: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=100000),
                     sort: str | None = None, descending: bool = False,
                     fields: str | None = Query(None, description="comma-separated field names")):
    """Attribute table rows of a vector layer (a page, optionally sorted)."""
    return service.layer_attributes(layer_id, offset, limit, sort, descending,
                                    [f for f in fields.split(",") if f] if fields else None)


@add_data_router.post("/layers/{layer_id}/identify")
def identify_feature(layer_id: str, req: IdentifyRequest):
    """Which feature lies under a clicked point, and its attributes."""
    return service.identify(layer_id, req.x, req.y, req.tolerance, req.crs)


@add_data_router.get("/layers/{layer_id}/display")
def layer_display(layer_id: str, bins: int = Query(30, ge=1, le=1000)):
    """Ramp, statistics and histogram a window needs to draw a raster layer."""
    return service.layer_display(layer_id, bins)

# ======================================================================
# File · Export  (/file/export)
# ======================================================================
export_router = APIRouter(prefix="/export", tags=["File · Export"])


@export_router.get("/map-image/{layer_id}", response_class=Response)
def map_image(layer_id: str, ramp: str = "terrain", vmin: float | None = None,
              vmax: float | None = None, max_pixels: int | None = Query(None, gt=0)):
    """The layer drawn as a PNG."""
    return Response(service.map_image(layer_id, ramp, vmin, vmax, max_pixels), media_type="image/png")


@export_router.post("/elevations")
def export_elevations(req: ExportElevationsRequest):
    """Write the layer's elevations to a GeoTIFF."""
    return service.export_elevations(req.layer_id, req.path)


@export_router.get("/statistics/{layer_id}")
def export_statistics(layer_id: str, format: Literal["json", "csv"] = "json"):
    result = service.statistics(layer_id, format)
    if format == "csv":
        return Response(result, media_type="text/csv")
    return result

# ======================================================================
# File · Workspace  (/file/workspace)
# ======================================================================
workspace_router = APIRouter(prefix="/workspace", tags=["File · Workspace"])


@workspace_router.post("/reset")
def reset_workspace():
    """Panels, appearance and display settings back to defaults (layers stay)."""
    return service.reset_workspace()


@workspace_router.put("/fullscreen")
def fullscreen(req: FullscreenRequest):
    return service.set_fullscreen(req.enabled)


@workspace_router.post("/exit")
def exit_app():
    """Tells the UI whether there are unsaved changes before it closes."""
    return service.exit_info()

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
file_router = APIRouter(prefix="/file")


@add_data_router.get("/layers/{layer_id}/pixel")
def layer_pixel(layer_id: str, row: int = Query(ge=0), col: int = Query(ge=0)):
    """Return a raster cell's value and centre coordinates."""
    return service.pixel_value(layer_id, row, col)


file_router.include_router(project_router)
file_router.include_router(add_data_router)
file_router.include_router(export_router)
file_router.include_router(workspace_router)

