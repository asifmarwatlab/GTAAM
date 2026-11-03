"""View > Panes group (toggle buttons)."""
GROUP = {
    "label": "Display",
    "tools": [
        dict(id="pane-contents", label="Layers", icon="panel_left", kind="toggle",
             toggle="contents", tip="Layers"),

        dict(id="show-statistics", label="Statistics", icon="stats", kind="action",
               action="show_stats", tip="Show layer statistics and properties"),

        dict(id="pane-pixel", label="Pixel Inspector", icon="crosshair", kind="toggle",
             toggle="pixel_inspector", tip="Pixel Inspector"),

          dict(id="el-north", label="North Arrow", icon="north", kind="toggle",
                       toggle="north_arrow", tip="North Arrow"),
                       
          dict(id="el-scale", label="Scale Bar", icon="scalebar", kind="toggle",
                       toggle="scale_bar", tip="Scale Bar")
    ],
}
