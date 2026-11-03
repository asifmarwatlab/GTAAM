"""File > Add data group."""
GROUP = {
    "label": "Add Data",
    "tools": [
        dict(id="add-raster", label="Add Raster", icon="raster_add", kind="action",
             action="add_raster", tip="Add Raster"),

        dict(id="add-vector", label="Add Vector", icon="vector_add", kind="action",
             action="add_vector", tip="Add Vector"),

        dict(id="add-basemap", label="Add Basemap", icon="basemap", kind="action",
             action="add_basemap", tip="Add Basemap"),
    ],
}
