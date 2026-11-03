# terrain_client

Python client for the Terrain Studio API. Your PyQt6 code calls methods; it never builds URLs.

```python
from terrain_client import TerrainApi

api = TerrainApi()                                        # http://127.0.0.1:8000
layer  = api.file.add_raster(r"C:\data\ALPSMLC30_N033E073_DSM.tif")
result = api.analysis.slope(layer["id"])                  # creates a NEW layer
png    = api.file.map_image(result["layer"]["id"], ramp="slope")
```

## Use it in your PyQt6 project

1. Copy the `terrain_client/` folder next to your UI code. It needs only `pip install httpx`
   (and PyQt6, which you already have, for `terrain_client.qt`).
2. It does not import the backend, so the two projects stay independent.

## The rule: never call the API on the GUI thread

A call takes milliseconds to seconds. Run it with `run_async` so the window never freezes:

```python
from terrain_client.qt import run_async

run_async(api.analysis.slope, layer_id,
          on_success=self.on_slope_done,     # called with the result, in the GUI thread
          on_error=self.show_error,          # called with ApiError / ApiConnectionError
          on_finished=self.hide_spinner)     # always called last
```

Callbacks run in the thread that called `run_async`, so they can touch widgets safely.

Show a map image:

```python
def on_png(self, png: bytes):
    pm = QPixmap(); pm.loadFromData(png); self.label.setPixmap(pm)
run_async(api.file.map_image, layer_id, "terrain", on_success=on_png)
```

## Start and stop the backend from the app

```python
from terrain_client.launcher import BackendProcess

backend = BackendProcess(r"C:\path\to\terrain_backend")   # folder that contains main.py
api = TerrainApi(backend.start())                          # free port, waits until healthy
...
backend.stop()                                             # in closeEvent / aboutToQuit
```

Or run it yourself with `py scripts/run_dev.py` and use `TerrainApi()`.

## Errors

```python
from terrain_client import ApiError, ApiConnectionError

try:
    api.analysis.slope("bad-id")
except ApiError as e:                 # the backend said no
    e.status, e.code, e.message       # 404, "layer_not_found", "Layer 'bad-id' does not exist."
except ApiConnectionError as e:       # backend not running / timed out
    ...
```

`e.message` is written for users, so show it directly in a status bar or message box.
Common codes: `layer_not_found`, `not_a_raster`, `invalid_value`, `validation_error`,
`no_region`, `no_edits`, `no_selection`, `job_not_found`, `job_failed`.

## Slow work (background jobs)

```python
job = api.mosaic.preview(background=True)        # returns at once: {"job_id": "..."}
run_async(api.jobs.wait, job["job_id"], on_progress=...)   # waits in a worker thread
```

## Every method

Tools that make something return `{"layer": {...}, "statistics": {...}}`. The new layer shows
up in `api.file.layers()`. Nothing ever overwrites an existing layer.

| Tab | Methods |
|---|---|
| `api.file` | `project_info` `new_project` `open_project` `save_project` `save_project_as` · `add_raster` `add_vector` `add_basemap` `layers` `reorder_layers` `update_layer` `remove_layer` `layer_geojson` · `map_image` `export_elevations` `statistics` · `reset_workspace` `set_fullscreen` `exit_app` |
| `api.view` | `explore` `full_extent` `zoom_in` `zoom_out` `zoom_to_layer` `update_viewport` · `panes` `set_pane` · `appearance` `update_appearance` `colour_ramps` · `display` `update_display` `hillshade_image` `slope_image` `contours` `reference_grid` `add_annotation` `remove_annotation` |
| `api.analysis` | `distance` `area` `elevation_profile` · `layer_statistics` `histogram` `nodata_check` `outlier_check` · `hillshade` `slope` `aspect` `curvature` · `contours` `roughness` `tpi` `ruggedness` |
| `api.tools` | `clip` `resample` `reproject` `fill_nodata` · `identify` `pixel` `properties` `metadata` · `options` `update_options` `shortcuts` `about` |
| `api.editing` | `draw_region` `regions` `select_region` `delete_selected` `clear_all` · `raise_lower` `smooth` `flatten` `fill_sinks` · `pending` `preview` `compare` `discard` · `apply` `export_edited_dem` |
| `api.mosaic` | `select_dems` `selection` · `difference_map` `seamline` · `blend_settings` `set_blend_settings` `preview` `apply` · `export_elevations` |
| `api.jobs` | `list` `get` `wait` |
| `api` | `health` `is_alive` `close` |

Every method has a docstring; in VS Code hover over it, or press Ctrl+Space after `api.analysis.`.

## Keeping it in step with the backend

`tests/client/test_client.py` calls every method against the real backend and then checks the
backend's own OpenAPI list: if an endpoint is added without a client method, that test fails
and names it. Adding a backend feature therefore means adding one client method (3 lines).

## Example

`examples/qt_example.py` is a small working window: open a DEM, run Slope/Hillshade, see the
result. `py examples/qt_example.py --backend-dir C:\path\to\terrain_backend`
