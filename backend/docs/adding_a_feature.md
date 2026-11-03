# Adding a feature without disturbing anything

## A. New button in an existing group (e.g. "Relief" in Terrain Derivatives)

1. Maths: `core/terrain/relief.py` with `compute_relief(dem) -> np.ndarray`.
2. Service: add `relief()` to `services/analysis_service.py`
   (copy `roughness()`: get layer, call core, `_derive(...)`).
3. Endpoint: add 3 lines in the "Terrain Derivatives" section of `routes/analysis_routes.py`.
4. Test: `tests/core/test_terrain.py` (known answer) and add the path to the parametrised
   list in `tests/routes/test_analysis_tools.py`.

Existing endpoints are not touched.

## B. New group in an existing tab

1. In `routes/<tab>_routes.py` add a section with
   `<group>_router = APIRouter(prefix="/<group>", tags=[...])`.
2. Add `<tab>_router.include_router(<group>_router)` at the bottom of that file.

## C. New tab (e.g. Hydrology)  - the "add a blueprint" recipe

1. Create `routes/hydrology_routes.py` (with `hydrology_router = APIRouter(prefix="/hydrology")`),
   `services/hydrology_service.py` and `schemas/hydrology_schemas.py`. Copy a small tab as a template.
2. Register it: import `hydrology_router` in `main.py` and add `("hydrology", hydrology_router)` to `BLUEPRINTS`.

## D. A breaking change to an existing endpoint

Do not edit it. Add a `v2` router and mount it at `/api/v2`. Version 1 keeps working for the UI
that still uses it.

## Rules that keep it clean

- Maths goes in `core/` and must run in a plain Python script (no FastAPI, no layer ids).
- A routes file never imports another routes file. Shared logic goes to `core/` or `shared/`.
- Buttons that appear on two tabs (Hillshade, Slope, Pixel Inspector) call the same `core`
  function from both services; the maths exists once.
- Keep route functions to a few lines. If a route grows, the logic belongs in the service.
