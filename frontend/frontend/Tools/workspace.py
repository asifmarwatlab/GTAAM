"""Tools > Workspace group."""
GROUP = {
    "label": "Workspace",
    "tools": [
        dict(id="options", label="Options", icon="gear", kind="dialog", run_label="OK",
             tip="Application options",
             fields=[
                 dict(type="combo", label="Display units", options=["Metres", "Feet"]),
                 dict(type="combo", label="Coordinate format", options=["Projected (E / N)", "Geographic (lat / lon)"]),
                 dict(type="check", label="Show tooltips", value=True),
                 dict(type="check", label="Confirm before discarding previews", value=True),
             ]),
        dict(id="shortcuts", label="Shortcuts", icon="keyboard", kind="dialog", run_label="Close",
             tip="Keyboard shortcuts",
             fields=[dict(type="info", text=(
                 "Ctrl+K  Search tools\nF11  Fullscreen workspace\nCtrl+S  Save project\n"
                 "Ctrl+O  Open project\nEsc  Cancel drawing / close search\n"
                 "+ / -  Zoom in / out (map focused)\nDelete  Remove selected region\n"
                 "Mouse wheel  Zoom   ·   Drag  Pan"))]),
        dict(id="about", label="About", icon="info", kind="dialog", run_label="Close",
             tip="About A-GTAAM",
             fields=[dict(type="info", text=(
                 "A-GTAAM Terrain Workspace\nAI-enabled Geospatial Terrain Analytics & "
                 "Adaptive Modification\n\nInterface preview built with PyQt6.\n"
                 "Processing back-ends are not connected yet."))]),
    ],
}
