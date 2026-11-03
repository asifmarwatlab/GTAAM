"""View > Navigate group."""
GROUP = {
    "label": "Navigate",
    "tools": [
        dict(id="explore", label="Explore", icon="hand", kind="action", action="mode_explore",
             tip="Explore"),
             
        dict(id="full-extent", label="Full Extent", icon="fullscreen", kind="action",
             action="full_extent", tip="Full Extent"),

          dict(id="bookmark", label="Bookmark", icon="bookmark", kind="toast",
               tip="Bookmark"),

        dict(id="zoom-in", label="Zoom In", icon="plus", kind="action",
             action="zoom_in", tip="Zoom In"),

        dict(id="zoom-out", label="Zoom Out", icon="minus", kind="action",
             action="zoom_out", tip="Zoom Out"),

          
    ],
}
