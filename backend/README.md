# Terrain Studio API (A-GTAAM backend)

FastAPI backend for the Terrain Studio / DEM analytics desktop app. The ribbon is the map:
**tab = module, ribbon group = `routes/<group>.py`, button = one endpoint.**

## Run it (Windows)

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
py scripts/run_dev.py
```

Open http://127.0.0.1:8000/docs - every ribbon button is there, grouped by tab and group,
and you can try each one in the browser.

Run the tests: `py -m pytest`

## Project layout

```
main.py            starts FastAPI, registers the six tab routers (like app.py in Flask)
config.py          settings (pydantic-settings, TERRAIN_* env vars, .env)
routes/            HTTP layer - one file per ribbon tab: <tab>_routes.py
services/          business logic - one file per tab: <tab>_service.py
schemas/           request/response shapes - <tab>_schemas.py + common.py
core/              MATHS, no FastAPI: raster/ terrain/ stats/ measure/ editing/ mosaic/ render/
shared/            layer_store, project_store, jobs, errors, logging
terrain_client/    Python client for the PyQt6 side (copy this folder into the UI project)
tests/             core/ (maths), routes/ (endpoints), client/ (client vs the real backend)
scripts/           run_dev.py, qgis_compare.py
docs/              architecture.md, adding_a_feature.md
```

## From the PyQt6 side

Use `terrain_client` - see `terrain_client/README.md`:

```python
from terrain_client import TerrainApi
api = TerrainApi()
layer = api.file.add_raster(r"C:\data\dem.tif")
result = api.analysis.slope(layer["id"])
```

## Typical first session

```
POST /api/v1/file/add-data/raster          {"path": "C:/data/ALPSMLC30_N033E073_DSM.tif"}   -> layer id
GET  /api/v1/analysis/quality-statistics/layer-statistics/{id}
POST /api/v1/analysis/surface-analysis/slope   {"layer_id": "{id}"}                          -> new layer
GET  /api/v1/file/export/map-image/{newid}?ramp=slope                                        -> PNG
POST /api/v1/file/export/elevations        {"layer_id": "{newid}", "path": "C:/out/slope.tif"}
```

Then compare with QGIS: `py scripts/qgis_compare.py out/slope.tif qgis_slope.tif`

## Endpoint map

| Tab | Group | Buttons |
|---|---|---|
| File | project | New, Open, Save, Save As |
| | add_data | Add Raster, Add Vector (GeoJSON), Add Basemap, layer list/rename/opacity/order/remove |
| | export | Map Image (PNG), Elevations (GeoTIFF), Statistics (JSON/CSV) |
| | workspace | Reset, Fullscreen, Exit |
| View | navigate | Explore, Full Extent, Zoom In/Out, Zoom to Layer |
| | panes | Contents, Statistics, Pixel Inspector |
| | appearance | Colour Ramp, North Arrow, Scale Bar, Layer Label |
| | display | Hillshade, Slope, Contours, Regions, Reference Grid, Annotation |
| Analysis | measure | Distance, Area, Elevation Profile |
| | quality_statistics | Layer Statistics, Histogram, NoData Check, Outlier Check |
| | surface_analysis | Hillshade, Slope, Aspect, Curvature |
| | terrain_derivatives | Contours, Roughness, TPI, Ruggedness |
| Tools | data_management | Clip, Resample, Reproject, Fill NoData |
| | inspect | Identify, Pixel Inspector, Properties, Metadata |
| | workspace | Options, Shortcuts, About |
| Terrain Editing | selection | Draw Region, Select Region, Delete Selected, Clear All |
| | modify_terrain | Raise/Lower, Smooth, Flatten, Fill Sinks (queued) |
| | review | Preview Changes, Compare, Discard |
| | output | Apply Edits (new layer), Export Edited DEM |
| Terrain Mosaic | input | Select DEMs |
| | overlap_analysis | Difference Map, Create Seamline |
| | mosaic | Blend Settings, Preview Mosaic, Apply Mosaic |
| | output | Export Elevations |

## Notes

- Tools never overwrite a layer; they add a new one (`derived_from` points to the source).
- Derived layers exist in memory until exported. Saved projects (`.json`) keep layers that have a file.
- Slope/aspect/hillshade/curvature use Horn's 3x3 method with real metre cell sizes, also for
  lat/lon DEMs such as AW3D30. Validate against QGIS with `scripts/qgis_compare.py`.
- Vector layers: GeoJSON only for now.
