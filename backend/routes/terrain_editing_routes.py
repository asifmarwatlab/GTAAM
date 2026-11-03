"""Terrain Editing tab routes (/terrain-editing).

Thin HTTP layer: read the request, call services/terrain_editing_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from fastapi import status
from schemas.common import DerivedLayerResult
from schemas.terrain_editing_schemas import ExportEditedRequest, FillSinksRequest, FlattenRequest, LayerRequest, RaiseLowerRequest, RegionCreate, RegionSelect, SmoothRequest
from services import terrain_editing_service as service


# ======================================================================
# Terrain Editing · Selection  (/terrain-editing/selection)
# ======================================================================
selection_router = APIRouter(prefix="/selection", tags=["Terrain Editing · Selection"])


@selection_router.post("/draw-region", status_code=status.HTTP_201_CREATED)
def draw_region(req: RegionCreate):
    return service.draw_region(req.layer_id, req.polygon, req.name)


@selection_router.get("/regions/{layer_id}")
def list_regions(layer_id: str):
    return service.list_regions(layer_id)


@selection_router.post("/select-region")
def select_region(req: RegionSelect):
    return service.select_regions(req.layer_id, req.region_ids)


@selection_router.post("/delete-selected")
def delete_selected(req: LayerRequest):
    return service.delete_selected(req.layer_id)


@selection_router.post("/clear-all")
def clear_all(req: LayerRequest):
    return service.clear_all(req.layer_id)

# ======================================================================
# Terrain Editing · Modify Terrain  (/terrain-editing/modify-terrain)
# ======================================================================
modify_terrain_router = APIRouter(prefix="/modify-terrain", tags=["Terrain Editing · Modify Terrain"])


@modify_terrain_router.post("/raise-lower")
def raise_lower(req: RaiseLowerRequest):
    """Queues the edit. Nothing changes until Apply."""
    return service.queue(req.layer_id, "raise_lower", {"amount": req.amount}, req.region_ids)


@modify_terrain_router.post("/smooth")
def smooth(req: SmoothRequest):
    return service.queue(req.layer_id, "smooth", {"iterations": req.iterations}, req.region_ids)


@modify_terrain_router.post("/flatten")
def flatten(req: FlattenRequest):
    return service.queue(req.layer_id, "flatten", {"elevation": req.elevation}, req.region_ids)


@modify_terrain_router.post("/fill-sinks")
def fill_sinks(req: FillSinksRequest):
    return service.queue(req.layer_id, "fill_sinks", {}, req.region_ids)

# ======================================================================
# Terrain Editing · Review  (/terrain-editing/review)
# ======================================================================
review_router = APIRouter(prefix="/review", tags=["Terrain Editing · Review"])


@review_router.get("/pending/{layer_id}")
def pending(layer_id: str):
    return service.pending(layer_id)


@review_router.post("/preview")
def preview(req: LayerRequest):
    return service.preview(req.layer_id)


@review_router.post("/compare")
def compare(req: LayerRequest):
    return service.compare(req.layer_id)


@review_router.post("/discard")
def discard(req: LayerRequest):
    return service.discard(req.layer_id)

# ======================================================================
# Terrain Editing · Output  (/terrain-editing/output)
# ======================================================================
output_router = APIRouter(prefix="/output", tags=["Terrain Editing · Output"])


@output_router.post("/apply", response_model=DerivedLayerResult)
def apply_edits(req: LayerRequest):
    """Creates a new '(edited)' layer. The original stays untouched."""
    return service.apply(req.layer_id)


@output_router.post("/export-edited-dem")
def export_edited_dem(req: ExportEditedRequest):
    return service.export_edited(req.layer_id, req.path)

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
terrain_editing_router = APIRouter(prefix="/terrain-editing")
terrain_editing_router.include_router(selection_router)
terrain_editing_router.include_router(modify_terrain_router)
terrain_editing_router.include_router(review_router)
terrain_editing_router.include_router(output_router)
