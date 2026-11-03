"""Analysis > Measure group."""
GROUP = {
    "label": "Measure",
    "tools": [
        dict(id="measure-distance", label="Distance", icon="ruler", kind="panel",
             tip="Distance",
             fields=[
                 dict(type="combo", label="Units", options=["Metres", "Kilometres", "Feet", "Miles"]),
                 dict(type="check", label="Snap to pixel centres", value=True),
                 dict(type="check", label="Show elevation difference", value=True),
             ]),

        dict(id="measure-area", label="Area", icon="area", kind="panel",
             tip="Area",
             fields=[
                 dict(type="combo", label="Units", options=["Square metres", "Hectares", "Square kilometres"]),
                 dict(type="check", label="Use planimetric area", value=True),
             ]),

        dict(id="measure-profile", label="Elevation Profile", icon="profile", kind="panel",
             tip="Elevation Profile",
             fields=[
                 dict(type="layer", label="Raster layer"),
                 dict(type="slider", label="Samples along line", min=20, max=1000, value=200),
                 dict(type="check", label="Vertical exaggeration", value=False),
             ]),
    ],
}
