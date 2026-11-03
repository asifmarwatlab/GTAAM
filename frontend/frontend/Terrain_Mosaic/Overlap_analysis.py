"""Terrain Mosaic > Overlap analysis group."""
GROUP = {
    "label": "Overlap Analysis",
    "tools": [
        dict(id="difference", label="Difference Map", icon="difference", kind="panel",
             run_label="Create", tip="Difference Map",
             fields=[
                 dict(type="layer", label="Reference DEM"),
                 dict(type="layer", label="Compared DEM"),
                 dict(type="combo", label="Output ramp", options=["Diverging (blue-red)", "Greyscale"]),
             ]),
        dict(id="seamline", label="Create Seamline", icon="seamline", kind="panel",
             run_label="Create", tip="Create Seamline",
             fields=[
                 dict(type="combo", label="Method", options=["Minimum difference path", "Shortest path", "Manual"]),
                 dict(type="slider", label="Smoothing", min=0, max=100, value=30, suffix=" %"),
             ]),
    ],
}
