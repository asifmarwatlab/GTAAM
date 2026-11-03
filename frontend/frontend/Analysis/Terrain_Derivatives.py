"""Analysis > Surface analysis group."""
GROUP = {
    "label": "Terrain Derivatives",
    "tools": [
        dict(id="an-hillshade", label="Hillshade", icon="sun", kind="panel",
             handler="terrain_derivative", run_label="Run",
             tip="Hillshade",
             fields=[
                 dict(type="layer", label="Input DEM"),
                 dict(type="slider", label="Azimuth", min=0, max=360, value=315, suffix="°"),
                 dict(type="slider", label="Altitude", min=0, max=90, value=45, suffix="°"),
                 dict(type="spin", label="Z factor", min=0.1, max=100, value=1.0, step=0.1, decimals=1),
             ]),
        dict(id="an-slope", label="Slope", icon="slope", kind="panel",
             handler="terrain_derivative", run_label="Run",
             tip="Slope",
             fields=[
                 dict(type="layer", label="Input DEM"),
                 dict(type="combo", label="Output units", options=["Degrees", "Percent rise"]),
             ]),
        dict(id="an-aspect", label="Aspect", icon="compass", kind="panel",
             handler="terrain_derivative", run_label="Run",
             tip="Aspect",
             fields=[
                 dict(type="layer", label="Input DEM"),
                 dict(type="check", label="Flat areas as -1", value=True),
             ]),
        dict(id="an-curvature", label="Curvature", icon="contours", kind="panel",
             handler="terrain_derivative", run_label="Run",
             tip="Curvature",
             fields=[
                 dict(type="layer", label="Input DEM"),
             ]),
        dict(id="an-contours", label="Contours", icon="contours", kind="panel",
                     handler="terrain_derivative", run_label="Create",
                     tip="Contours",
                     fields=[
                         dict(type="layer", label="Input DEM"),
                         dict(type="spin", label="Interval", min=1, max=2000, value=250, suffix="m"),
                         dict(type="spin", label="Base elevation", min=-100000, max=100000, value=0, suffix="m"),
                     ]),
    ],
}
