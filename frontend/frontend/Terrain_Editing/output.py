"""Terrain Editing > Output group."""
GROUP = {
    "label": "Output",
    "tools": [
        dict(id="edit-apply", label="Apply Edits", icon="check", kind="panel", run_label="Apply",
             tip="Apply Edits",
             fields=[
                 dict(type="text", label="Output name", value="Upper_Indus_DEM_edited.tif"),
                 dict(type="check", label="Add result to map", value=True),
             ]),
        dict(id="edit-export", label="Export Edited DEM", icon="export", 
             kind="dialog", run_label="Export", tip="Export Edited DEM",
             fields=[
                 dict(type="combo", label="Format", options=["GeoTIFF (.tif)", "ASCII Grid (.asc)"]),
                 dict(type="text", label="NoData value", value="-9999"),
             ]),
    ],
}
