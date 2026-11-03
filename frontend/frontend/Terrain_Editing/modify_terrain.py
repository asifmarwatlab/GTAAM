"""Terrain Editing > Modify terrain group."""
GROUP = {
    "label": "Modify Terrain",
    "tools": [
        dict(id="edit-raise", label="Raise / Lower", icon="raise", kind="panel",
             handler="preview_edit", run_label="Preview", tip="Raise / Lower",
             fields=[
                 dict(type="spin", label="Elevation change", min=-2000, max=2000, value=25, suffix="m"),
                 dict(type="slider", label="Edge feather", min=0, max=500, value=60, suffix=" m"),
             ]),
        dict(id="edit-smooth", label="Smooth", icon="smooth", kind="panel",
             handler="preview_edit", run_label="Preview", tip="Smooth",
             fields=[
                 dict(type="slider", label="Iterations", min=1, max=20, value=3),
                 dict(type="combo", label="Kernel", options=["Gaussian", "Mean", "Median"]),
             ]),
        dict(id="edit-flatten", label="Flatten", icon="flatten", kind="panel",
             handler="preview_edit", run_label="Preview", tip="Flatten",
             fields=[
                 dict(type="spin", label="Target elevation", min=0, max=9000, value=3000, suffix="m"),
                 dict(type="slider", label="Edge feather", min=0, max=500, value=40, suffix=" m"),
             ]),
        dict(id="edit-fill", label="Fill Sinks", icon="drop", kind="panel",
             handler="preview_edit", run_label="Preview", tip="Fill Sinks",
             fields=[dict(type="spin", label="Z limit", min=0, max=500, value=10, suffix="m")]),
    ],
}
