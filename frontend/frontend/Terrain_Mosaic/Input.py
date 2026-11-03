"""Terrain Mosaic > Input group."""
GROUP = {
    "label": "Input",
    "tools": [
        dict(id="mosaic-input", label="Select DEMs", icon="grid", kind="dialog",
             handler="select_dems", run_label="Use selection", tip="Select DEMs",
             fields=[
                 dict(type="info", text="Choose the DEMs that will be combined into the mosaic."),
                 dict(type="layers", label="Input DEMs", key="dems",
                      checked=["Upper_Indus_DEM.tif", "DEM_East.tif"]),
             ]),
    ],
}
