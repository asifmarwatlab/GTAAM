"""View tab routes (/view).

Thin HTTP layer: read the request, call services/view_service.py, return the result.
No business logic here. One section per ribbon group.
"""
from fastapi import APIRouter

from fastapi import Response, status
from schemas.common import Message
from schemas.view_schemas import AnnotationCreate, AppearanceUpdate, DisplayToggles, ModeRequest, PaneUpdate, ViewportUpdate, ZoomRequest
from services import view_service as service


# ======================================================================
# View · Navigate  (/view/navigate)
# ======================================================================
navigate_router = APIRouter(prefix="/navigate", tags=["View · Navigate"])


@navigate_router.post("/explore")
def explore(req: ModeRequest | None = None):
    """Switch the pointer tool (default: explore / pan)."""
    return service.set_mode(req.mode if req else "explore")


@navigate_router.get("/full-extent")
def full_extent():
    return service.full_extent()


@navigate_router.post("/zoom-in")
def zoom_in(req: ZoomRequest | None = None):
    return service.zoom((req or ZoomRequest()).factor, "in")


@navigate_router.post("/zoom-out")
def zoom_out(req: ZoomRequest | None = None):
    return service.zoom((req or ZoomRequest()).factor, "out")


@navigate_router.get("/zoom-to-layer/{layer_id}")
def zoom_to_layer(layer_id: str):
    return service.zoom_to_layer(layer_id)


@navigate_router.put("/viewport")
def update_viewport(req: ViewportUpdate):
    """The UI reports its centre/scale so zoom-in/out can stay in step."""
    return service.update_viewport(req.center, req.scale)

# ======================================================================
# View · Panes  (/view/panes)
# ======================================================================
panes_router = APIRouter(prefix="/panes", tags=["View · Panes"])


@panes_router.get("")
def get_panes():
    """Which panels are open: contents, statistics, pixel_inspector."""
    return service.get_panes()


@panes_router.put("/{pane}")
def set_pane(pane: str, req: PaneUpdate):
    return service.set_pane(pane, req.visible)

# ======================================================================
# View · Appearance  (/view/appearance)
# ======================================================================
appearance_router = APIRouter(prefix="/appearance", tags=["View · Appearance"])


@appearance_router.get("")
def get_appearance():
    return service.get_appearance()


@appearance_router.put("")
def update_appearance(req: AppearanceUpdate):
    return service.update_appearance(req.model_dump(exclude_none=True))


@appearance_router.get("/colour-ramps")
def colour_ramps():
    return service.colour_ramps()

# ======================================================================
# View · Display  (/view/display)
# ======================================================================
display_router = APIRouter(prefix="/display", tags=["View · Display"])


@display_router.get("")
def get_display():
    return service.get_display()


@display_router.put("")
def update_display(req: DisplayToggles):
    """Switch Regions / Reference Grid / Annotation on or off."""
    return service.update_display(req.model_dump(exclude_none=True))


@display_router.get("/hillshade/{layer_id}", response_class=Response)
def hillshade(layer_id: str, azimuth: float = 315, altitude: float = 45, z_factor: float = 1.0):
    return Response(service.hillshade_image(layer_id, azimuth, altitude, z_factor), media_type="image/png")


@display_router.get("/slope/{layer_id}", response_class=Response)
def slope(layer_id: str, ramp: str = "slope"):
    return Response(service.slope_image(layer_id, ramp), media_type="image/png")


@display_router.get("/contours/{layer_id}")
def contours(layer_id: str, interval: float = 100.0, base: float = 0.0):
    return service.contours(layer_id, interval, base)


@display_router.get("/reference-grid/{layer_id}")
def reference_grid(layer_id: str, spacing: float):
    return service.reference_grid(layer_id, spacing)


@display_router.post("/annotations", status_code=status.HTTP_201_CREATED)
def add_annotation(req: AnnotationCreate):
    return service.add_annotation(req.x, req.y, req.text)


@display_router.delete("/annotations/{note_id}", response_model=Message)
def remove_annotation(note_id: str):
    service.remove_annotation(note_id)
    return Message(message="Annotation removed.")

# ======================================================================
# Tab router - registered once in main.py
# ======================================================================
view_router = APIRouter(prefix="/view")
view_router.include_router(navigate_router)
view_router.include_router(panes_router)
view_router.include_router(appearance_router)
view_router.include_router(display_router)
