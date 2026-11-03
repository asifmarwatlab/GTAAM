"""Tools > Data management group."""
GROUP = {
    "label": "Data Management",
    "tools": [
        dict(id="dm-clip", label="Clip", icon="clip", kind="panel", run_label="Clip",
             tip="Clip a raster to an extent or editing region",
             fields=[
                 dict(type="layer", label="Input raster"),
                 dict(type="combo", label="Clip to", options=["Current map extent", "Editing regions", "Custom extent"]),
             ]),
        dict(id="dm-resample", label="Resample", icon="resample", kind="panel", run_label="Resample",
             tip="Change the cell size of a raster",
             fields=[
                 dict(type="layer", label="Input raster"),
                 dict(type="spin", label="Cell size", min=1, max=1000, value=10, suffix="m"),
                 dict(type="combo", label="Method", options=["Bilinear", "Cubic", "Nearest neighbour"]),
             ]),
        dict(id="dm-reproject", label="Reproject", icon="reproject", kind="panel", run_label="Reproject",
             tip="Transform a raster to another coordinate system",
             fields=[
                 dict(type="layer", label="Input raster"),
                 dict(type="combo", label="Target CRS",
                      options=["WGS 84 / UTM 43N (EPSG:32643)", "WGS 84 (EPSG:4326)", "WGS 84 / UTM 42N (EPSG:32642)"]),
             ]),
        dict(id="dm-fill", label="Fill NoData", icon="drop", kind="panel",
             run_label="Fill", tip="Interpolate over NoData pixels",
             fields=[
                 dict(type="layer", label="Input raster"),
                 dict(type="slider", label="Search distance", min=1, max=100, value=10, suffix=" px"),
             ]),
    ],
}
