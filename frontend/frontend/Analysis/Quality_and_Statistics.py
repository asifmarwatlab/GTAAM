"""Analysis > Quality & Statistics group."""
GROUP = {
    "label": "Quality & Statistics",
    "tools": [
        dict(id="layer-statistics", label="Layer Statistic & Properties", icon="stats", kind="action",
             action="show_stats", tip="Layer Statistics & Properties"),

        dict(id="histogram", label="Histogram", icon="stats", kind="panel",
             handler="histogram", run_label="Show histogram",
             result_note="Draws the distribution of pixel values in a chart window.",
             tip="Histogram",
             fields=[
                 dict(type="layer", label="Raster layer"),
                 dict(type="slider", label="Bins", min=10, max=100, value=30),
                 dict(type="check", label="Logarithmic counts", value=False),
             ]),
        dict(id="nodata-check", label="NoData Check", icon="check", kind="panel",
             handler="nodata_check", run_label="Check",
             result_note="Counts empty (NoData) cells and the rows and columns they touch.",
             tip="NoData Check",
             fields=[
                 dict(type="layer", label="Raster layer"),
                 dict(type="info", text="NoData cells are detected automatically from the raster."),
             ]),

        dict(id="outlier-check", label="Outlier Check", icon="eye", kind="panel",
             handler="outlier_check", run_label="Check",
             result_note="Reports cells outside the normal range (IQR rule or Z-score).",
             tip="Outlier Check",
             fields=[
                 dict(type="layer", label="Raster layer"),
                 dict(type="combo", label="Method", options=["IQR", "Z-score"], key="method"),
                 dict(type="spin", label="Threshold", min=0.5, max=10, value=1.5, step=0.5,
                      decimals=1, key="threshold"),
             ]),
    ],
}
