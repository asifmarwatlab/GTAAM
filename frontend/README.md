# A-GTAAM Terrain Workspace  (PyQt6 interface preview)

AI-enabled Geospatial Terrain Analytics & Adaptive Modification - frontend only.
All panels, tabs, ribbon tools, layer tree, statistics, map canvas and pixel
inspector are interactive.  Processing back-ends are intentionally **not**
connected yet (tools capture their settings and show a confirmation).

## How to run

Python 3.12 or newer is recommended (numpy 2.4 / scipy 1.17 need 3.11+).

### Windows (PowerShell, from inside the A-GTAAM-Proj-o folder)
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python frontend\main.py

(If PowerShell blocks activation:  Set-ExecutionPolicy -Scope Process Bypass)

### macOS / Linux
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 frontend/main.py

### VS Code
Open the folder, choose the `.venv` interpreter (Ctrl+Shift+P > "Python: Select
Interpreter"), then press F5 ("A-GTAAM: run main.py").

## What you can do
* Switch ribbon tabs: File, View, Analysis, Tools, Terrain Editing, Terrain Mosaic.
* Ctrl+K - search every tool; Enter runs it.
* Contents pane: tick layers on/off, click a layer for statistics, `...` menu, filter box.
* Map: drag to pan, scroll to zoom, hover for the live pixel inspector, zoom buttons, scale menu.
* Terrain Editing > Draw Region: click vertices, double-click to finish, Esc cancels.
* Terrain Mosaic > Preview Mosaic / Terrain Editing > Preview Changes show the preview banner.
* File > Save / Open stores the interface state as JSON; Export > Map Image saves PNG/JPEG.
* Panels can be hidden (View > Panes) and resized by dragging the splitters.

## Where to change things later
| I want to...                          | Edit                                   |
|---------------------------------------|----------------------------------------|
| add / rename a ribbon button          | the module of that group, e.g. `frontend/Terrain_Mosaic/Mosaic.py` |
| add a brand-new action                | `frontend/ui/gui.py` -> add `act_<name>()`, reference it as `action="<name>"` |
| add an icon                           | `frontend/ui/panels/icon_generator.py` (`ICONS`) |
| change the application branding       | `frontend/ui/assets/` |
| change colours / text sizes           | `frontend/ui/styles.qss`              |
| layer tree & statistics panes         | `frontend/ui/panels/layer_statistics.py` |
| map canvas, overlays, footer          | `frontend/ui/panels/map_bar.py`        |
| replace the sample data with real DEMs| `SampleWorkspace` in `frontend/ui/panels/layer_statistics.py` (use rasterio) |

Each tab is a package; each ribbon group is one module inside it:

    A-GTAAM_PROJECT - Copy/
      A-GTAAM-Proj-o/
        frontend/
          file/             Project, Add_data, Export, Workspace
          View/             Navigate, Panes, Appearance, display
          Analysis/         Measure, Quality_and_Statistics, surface_analysis, Terrain_derivatives
          Tools/            data_management, inspect, workspace
          Terrain_Editing/  selection, modify_terrain, review, output
          Terrain_Mosaic/   Input, Overlap_analysis, Mosaic, output
          ui/               Application window, panels, styles, assets
          main.py           Application entry point

`requirements.txt`, this README, `.vscode/`, and the virtual environment remain at the project root. The backend is a separate repo (AGTAAM-Backend), kept in a `backend` folder next to this one; this repo no longer bundles a copy.

Notes
* requirements.txt lists both PyQt5 and PyQt6 (as supplied). The app forces PyQt6
  (`QT_API=pyqt6`) so they never mix.
* `__pycache__/` folders are created automatically the first time you run the app.




Running with the backend
* Put the backend repo in a folder called `backend` next to this repo's folder
  (or write its path in `frontend/backend_dir.txt`, or set AGTAAM_BACKEND_DIR).
* Create its virtual environment and install its requirements once, then just run
  `py main.py` from the `frontend` folder: the app starts the backend itself.
