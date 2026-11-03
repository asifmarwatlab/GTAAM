"""Tools > Inspect group."""
GROUP = {
    "label": "Inspect",
    "tools": [
        dict(id="identify", label="Identify", icon="cursor", kind="action", action="mode_explore",
             tip="Move the pointer over the map to inspect a pixel"),
        dict(id="inspect-pixel", label="Pixel Inspector", icon="crosshair", kind="toggle",
             toggle="pixel_inspector", tip="Show or hide the live pixel inspector"),
        dict(id="inspect-properties", label="Properties", icon="table",
             kind="action", action="show_stats", tip="Show properties of the selected layer"),
        dict(id="inspect-metadata", label="Metadata", icon="info", kind="dialog",
             run_label="Close", tip="Dataset metadata",
             fields=[dict(type="info", text=(
                 "Upper_Indus_DEM.tif\n\nDriver: GTiff\nSize: 768 × 512 × 1 band\n"
                 "Data type: Float32\nCRS: WGS 84 / UTM 43N (EPSG:32643)\nPixel size: 10 × 10 m\n"
                 "Origin: 480,000.00 E · 3,806,120.00 N"))]),
    ],
}
