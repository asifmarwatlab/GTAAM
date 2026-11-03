"""Terrain Editing > Review group."""
GROUP = {
    "label": "Review",
    "tools": [
        dict(id="review-preview", label="Preview Changes", icon="eye", kind="action",
             action="preview_edit", tip="Preview Changes"),

        dict(id="review-compare", label="Compare", icon="compare", kind="panel",
             tip="Compare",
             fields=[
                 dict(type="combo", label="Mode", options=["Side by side", "Swipe", "Difference"]),
                 dict(type="check", label="Link map views", value=True),
             ]),
        dict(id="review-discard", label="Discard", icon="undo", kind="action",
             action="discard_preview", tip="Discard"),
    ],
}
