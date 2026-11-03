"""Terrain Mosaic > Mosaic group."""
GROUP = {
    "label": "Mosaic",
    "tools": [
        dict(id="mosaic-blend", label="Blend Settings", icon="blend", kind="panel",
             run_label="Save settings", tip="Blend Settings",
             fields=[
                 dict(type="combo", label="Blend method", options=["Feather", "Average", "First", "Last", "Minimum", "Maximum"]),
                 dict(type="slider", label="Blend width", min=0, max=1000, value=150, suffix=" m"),
                 dict(type="check", label="Match elevation bias in overlap", value=True),
             ]),
        dict(id="mosaic-preview", label="Preview Mosaic", icon="mosaic", kind="action",
             action="preview_mosaic", tip="Preview Mosaic"),
    ],
}
