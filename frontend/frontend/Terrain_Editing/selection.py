"""Terrain Editing > Selection group."""
GROUP = {
    "label": "Selection",
    "tools": [
        dict(id="draw-region", label="Draw Region", icon="draw", kind="action",
             action="draw_region", tip="Draw Region"),

        dict(id="select-region", label="Select Region", icon="select", kind="action",
             action="mode_select", tip="Select Region"),

        dict(id="delete-region", label="Delete Selected", icon="trash",
             kind="action", action="delete_region", tip="Delete Selected"),

        dict(id="clear-regions", label="Clear All", icon="close",
             kind="action", action="clear_regions", tip="Clear All"),
    ],
}
