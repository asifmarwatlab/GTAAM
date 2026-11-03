"""Tools tab routes (/tools).

Thin HTTP layer: read the request, call services/tools_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from schemas.common import DerivedLayerResult
from schemas.tools_schemas import ClipRequest, FillNoDataRequest, IdentifyRequest, OptionsUpdate, ReprojectRequest, ResampleRequest
from services import tools_service as service


# ======================================================================
# Tools · Data Management  (/tools/data-management)
# ======================================================================
data_management_router = APIRouter(prefix="/data-management", tags=["Tools · Data Management"])


@data_management_router.post("/clip", response_model=DerivedLayerResult)
def clip(req: ClipRequest):
    return service.clip(req.layer_id, req.bounds.as_tuple())


@data_management_router.post("/resample", response_model=DerivedLayerResult)
def resample(req: ResampleRequest):
    return service.resample(req.layer_id, req.cell_size, req.method)


@data_management_router.post("/reproject", response_model=DerivedLayerResult)
def reproject(req: ReprojectRequest):
    return service.reproject(req.layer_id, req.epsg, req.method)


@data_management_router.post("/fill-nodata", response_model=DerivedLayerResult)
def fill_nodata(req: FillNoDataRequest):
    return service.fill_nodata(req.layer_id, req.max_iterations)

# ======================================================================
# Tools · Inspect  (/tools/inspect)
# ======================================================================
inspect_router = APIRouter(prefix="/inspect", tags=["Tools · Inspect"])


@inspect_router.post("/identify")
def identify(req: IdentifyRequest):
    """Click on the map: value, row/column and pixel centre at that point."""
    return service.identify(req.layer_id, req.x, req.y)


@inspect_router.get("/pixel/{layer_id}")
def pixel_inspector(layer_id: str, x: float, y: float):
    """Same as identify but as a GET, for the live Pixel Inspector as the mouse moves."""
    return service.identify(layer_id, x, y)


@inspect_router.get("/properties/{layer_id}")
def properties(layer_id: str):
    return service.properties(layer_id)


@inspect_router.get("/metadata/{layer_id}")
def metadata(layer_id: str):
    return service.metadata(layer_id)

# ======================================================================
# Tools · Workspace  (/tools/workspace)
# ======================================================================
workspace_router = APIRouter(prefix="/workspace", tags=["Tools · Workspace"])


@workspace_router.get("/options")
def get_options():
    return service.get_options()


@workspace_router.put("/options")
def update_options(req: OptionsUpdate):
    return service.update_options(req.model_dump(exclude_none=True))


@workspace_router.get("/shortcuts")
def shortcuts():
    return service.shortcuts()


@workspace_router.get("/about")
def about():
    return service.about()

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
tools_router = APIRouter(prefix="/tools")
tools_router.include_router(data_management_router)
tools_router.include_router(inspect_router)
tools_router.include_router(workspace_router)
