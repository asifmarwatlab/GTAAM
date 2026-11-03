"""Terrain Mosaic tab routes (/terrain-mosaic).

Thin HTTP layer: read the request, call services/terrain_mosaic_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from fastapi import Response
from schemas.common import DerivedLayerResult
from schemas.terrain_mosaic_schemas import BlendSettings, ExportMosaicRequest, PairRequest, SelectDems
from services import terrain_mosaic_service as service


# ======================================================================
# Terrain Mosaic · Input  (/terrain-mosaic/input)
# ======================================================================
input_router = APIRouter(prefix="/input", tags=["Terrain Mosaic · Input"])


@input_router.post("/select-dems")
def select_dems(req: SelectDems):
    """Pick the DEM layers to merge. Reports whether they share a CRS and cell size."""
    return service.select_dems(req.layer_ids)


@input_router.get("/select-dems")
def get_selection():
    return service.get_selection()

# ======================================================================
# Terrain Mosaic · Overlap Analysis  (/terrain-mosaic/overlap-analysis)
# ======================================================================
overlap_analysis_router = APIRouter(prefix="/overlap-analysis", tags=["Terrain Mosaic · Overlap Analysis"])


@overlap_analysis_router.post("/difference-map", response_model=DerivedLayerResult)
def difference_map(req: PairRequest | None = None):
    req = req or PairRequest()
    return service.make_difference_map(req.layer_a, req.layer_b)


@overlap_analysis_router.post("/seamline", response_model=DerivedLayerResult)
def create_seamline(req: PairRequest | None = None):
    req = req or PairRequest()
    return service.make_seamline(req.layer_a, req.layer_b)

# ======================================================================
# Terrain Mosaic · Mosaic  (/terrain-mosaic/mosaic)
# ======================================================================
mosaic_router = APIRouter(prefix="/mosaic", tags=["Terrain Mosaic · Mosaic"])


@mosaic_router.get("/blend-settings")
def get_blend_settings():
    return service.get_blend()


@mosaic_router.put("/blend-settings")
def set_blend_settings(req: BlendSettings):
    return service.set_blend(req.method, req.feather_pixels)


@mosaic_router.post("/preview")
def preview_mosaic(response: Response, background: bool = False):
    """background=true returns a job_id (poll /api/v1/jobs/{id}) instead of waiting."""
    result = service.preview(background)
    if background:
        response.status_code = 202
    return result


@mosaic_router.post("/apply", response_model=DerivedLayerResult)
def apply_mosaic():
    return service.apply()

# ======================================================================
# Terrain Mosaic · Output  (/terrain-mosaic/output)
# ======================================================================
output_router = APIRouter(prefix="/output", tags=["Terrain Mosaic · Output"])


@output_router.post("/export-elevations")
def export_elevations(req: ExportMosaicRequest):
    return service.export_elevations(req.path)

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
terrain_mosaic_router = APIRouter(prefix="/terrain-mosaic")
terrain_mosaic_router.include_router(input_router)
terrain_mosaic_router.include_router(overlap_analysis_router)
terrain_mosaic_router.include_router(mosaic_router)
terrain_mosaic_router.include_router(output_router)
