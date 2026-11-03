"""Terrain Mosaic > Output group."""
GROUP = {
    "label": "Output",
    "tools": [
        dict(id="mosaic-apply", label="Apply Mosaic", icon="check", kind="panel",
             run_label="Apply", tip="Apply Mosaic",
             fields=[
                 dict(type="text", label="Output name", value="Mosaic_DEM.tif"),
                 dict(type="check", label="Add result to map", value=True),
             ]),
        dict(id="export-elevations", label="Export Elevations", icon="export", 
             kind="dialog", run_label="Export", tip="Export Elevations",
             fields=[
                 dict(type="layer", label="Layer"),
                 dict(type="combo", label="Format", options=["GeoTIFF (.tif)", "ASCII Grid (.asc)", "XYZ points (.csv)"]),
                 dict(type="text", label="NoData value", value="-9999"),
             ]),
    ],
}
