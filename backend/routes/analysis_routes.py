"""Analysis tab routes (/analysis).

Thin HTTP layer: read the request, call services/analysis_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from schemas.analysis_schemas import AspectRequest, AreaRequest, ContoursRequest, DistanceRequest, HillshadeRequest, LayerRequest, ProfileRequest, SlopeRequest
from schemas.common import DerivedLayerResult
from typing import Literal
from services import analysis_service as service


# ======================================================================
# Analysis · Measure  (/analysis/measure)
# ======================================================================
measure_router = APIRouter(prefix="/measure", tags=["Analysis · Measure"])


@measure_router.post("/distance")
def distance(req: DistanceRequest):
    """Length of a line in the chosen unit, plus the height difference between its ends."""
    return service.distance(req.layer_id, req.points, req.pixels, req.units, req.include_elevation, req.snap)


@measure_router.post("/area")
def area(req: AreaRequest):
    return service.area(req.layer_id, req.polygon)


@measure_router.post("/elevation-profile")
def elevation_profile(req: ProfileRequest):
    return service.elevation_profile(req.layer_id, req.line, req.samples)

# ======================================================================
# Analysis · Quality Statistics  (/analysis/quality-statistics)
# ======================================================================
quality_statistics_router = APIRouter(prefix="/quality-statistics", tags=["Analysis · Quality & Statistics"])


@quality_statistics_router.get("/layer-statistics/{layer_id}")
def layer_statistics(layer_id: str):
    return service.layer_statistics(layer_id)


@quality_statistics_router.get("/histogram/{layer_id}")
def histogram(layer_id: str, bins: int = 50):
    return service.get_histogram(layer_id, bins)


@quality_statistics_router.get("/nodata-check/{layer_id}")
def nodata_check(layer_id: str):
    return service.nodata(layer_id)


@quality_statistics_router.get("/outlier-check/{layer_id}")
def outlier_check(layer_id: str, method: Literal["iqr", "zscore"] = "iqr",
                  threshold: float | None = None):
    return service.outlier_check(layer_id, method, threshold)

# ======================================================================
# Analysis · Surface Analysis  (/analysis/surface-analysis)
# ======================================================================
surface_analysis_router = APIRouter(prefix="/surface-analysis", tags=["Analysis · Surface Analysis"])


@surface_analysis_router.post("/hillshade", response_model=DerivedLayerResult)
def hillshade(req: HillshadeRequest):
    return service.hillshade(req.layer_id, req.azimuth, req.altitude, req.z_factor)


@surface_analysis_router.post("/slope", response_model=DerivedLayerResult)
def slope(req: SlopeRequest):
    return service.slope(req.layer_id, req.units)


@surface_analysis_router.post("/aspect", response_model=DerivedLayerResult)
def aspect(req: AspectRequest):
    return service.aspect(req.layer_id, req.flat_as_minus_one)


@surface_analysis_router.post("/curvature", response_model=DerivedLayerResult)
def curvature(req: LayerRequest):
    return service.curvature(req.layer_id)

# ======================================================================
# Analysis · Terrain Derivatives  (/analysis/terrain-derivatives)
# ======================================================================
terrain_derivatives_router = APIRouter(prefix="/terrain-derivatives", tags=["Analysis · Terrain Derivatives"])


@terrain_derivatives_router.post("/contours", response_model=DerivedLayerResult)
def contours(req: ContoursRequest):
    """Adds a vector layer; fetch its lines from /file/add-data/layers/{id}/geojson."""
    return service.contours(req.layer_id, req.interval, req.base)


@terrain_derivatives_router.post("/roughness", response_model=DerivedLayerResult)
def roughness(req: LayerRequest):
    return service.roughness(req.layer_id)


@terrain_derivatives_router.post("/tpi", response_model=DerivedLayerResult)
def tpi(req: LayerRequest):
    return service.tpi(req.layer_id)


@terrain_derivatives_router.post("/ruggedness", response_model=DerivedLayerResult)
def ruggedness(req: LayerRequest):
    return service.ruggedness(req.layer_id)

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
analysis_router = APIRouter(prefix="/analysis")
analysis_router.include_router(measure_router)
analysis_router.include_router(quality_statistics_router)
analysis_router.include_router(surface_analysis_router)
analysis_router.include_router(terrain_derivatives_router)
