# New / Open / Save / Save As - how to use them in another DEM app

These four functions are already built and tested in this backend. A second app does
not copy the logic; it **talks to the backend**. Think of the backend as the kitchen:
your app (the dining room) only places orders.

## What you need
1. This backend repo (`_restructured`), running: `python -m uvicorn main:app --port 8765`
   (install first: `pip install -r requirements.txt`).
2. Your app must **load its layers through this backend** (`POST /api/v1/file/add-data/raster`).
   The project saves whatever layers the backend holds, so layers loaded any other way
   are not saved.

## The four orders (HTTP, base `http://127.0.0.1:8765/api/v1`)

| Action | Request | Notes |
|---|---|---|
| New | `POST /file/project/new` `{"name": "Untitled project"}` | clears all layers |
| Save | `POST /file/project/save` `{"path": "C:/x/mine.agtaam", "name": "mine", "gui": {...}}` | omit `path` to overwrite the current file |
| Save As | `POST /file/project/save-as` `{"path": "...", "name": "...", "gui": {...}}` | |
| Open | `POST /file/project/open` `{"path": "C:/x/mine.agtaam"}` | reply has `missing_layers` and your `gui` back |
| Is it unsaved? | `GET /file/project` | `dirty: true/false` |
| List layers (after Open) | `GET /file/add-data/layers` | rebuild your layer list from this |

* `gui` is a free-form dictionary for **your window's own state** (zoom, colour ramp,
  which layers are visible...). The backend stores it in the file and gives it back on Open.
* Saving also writes tool results (slope, hillshade, contours...) into a `<name>_data`
  folder next to the project file. Keep the file and that folder together.
* The project file is plain JSON (`.agtaam`); older `.json` projects still open.

## Python app, no HTTP code: use `terrain_client`
```python
from terrain_client import TerrainApi          # folder: terrain_client/
api = TerrainApi("http://127.0.0.1:8765")      # same address the backend runs on
api.file.new_project("Untitled project")
api.file.save_project_as(r"C:\work\mine.agtaam", gui={"zoom": 3}, name="mine")
info = api.file.open_project(r"C:\work\mine.agtaam")   # info["missing_layers"], info["gui"]
layers = api.file.layers()
```

## PyQt6 app: reuse the ready-made window part
`project_actions.py` (in this folder) is the exact code used in the A-GTAAM window:
"Save changes?" question, `*` in the title, Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S,
and rebuilding the layers after Open.

1. Copy `project_actions.py` into your `ui` folder.
2. `class MainWindow(ProjectMixin, QMainWindow):` and call `self._init_project_actions()`
   at the end of `__init__` (after the window is built).
3. Your window must provide what the file expects (rename these inside the file if yours differ):
   `api_post`, `api_get`, `api_get_bytes`, `show_toast`, `self.ws` (layer list with
   `reset/layers/regions/has_layer/layer/add_raster_image`), `self.map.canvas`,
   `self.map.set_project_name`, `self.map.tab_dot`, `_refresh_everything`,
   `_decode_raster_image`, `_regions_changed`, `project_name`, `project_path`.
4. Call `self.mark_dirty()` whenever the user changes something worth saving.

If your app is not PyQt6, use the HTTP table above; the window part is about 150 lines
and easy to rewrite.

## Quick test without any window
```
curl -X POST http://127.0.0.1:8765/api/v1/file/project/new -H "Content-Type: application/json" -d "{\"name\":\"t\"}"
curl -X POST http://127.0.0.1:8765/api/v1/file/add-data/raster -H "Content-Type: application/json" -d "{\"path\":\"C:/data/dem.tif\"}"
curl -X POST http://127.0.0.1:8765/api/v1/file/project/save-as -H "Content-Type: application/json" -d "{\"path\":\"C:/data/t.agtaam\"}"
```
Interactive docs for every endpoint: `http://127.0.0.1:8765/docs`.
