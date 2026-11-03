"""File > Export group."""
GROUP = {
    "label": "Export",
    "tools": [
        dict(id="export-map-image", label="Export Raster", icon="image", kind="action",
             action="export_image", tip="Export Raster"),
             
        dict(id="file-export-elevations", label="Export Vector", icon="export", kind="dialog",
             tip="Export Vector", run_label="Export",
             fields=[
                 dict(type="layer", label="Layer"),
                 dict(type="combo", label="Format", options=["GeoTIFF (.tif)", "ASCII Grid (.asc)", "XYZ points (.csv)"]),
                 dict(type="text", label="NoData value", value="-9999"),
             ]),
        
    ],
}
