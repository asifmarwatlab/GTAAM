"""View > Display group - layer visibility shortcuts (toggle = "layer:<id>")."""
GROUP = {
    "label": "Compare & Annotate",
    "tools": [

        dict(id="show-Swipe", label="Swipe", icon="swipe", size="large",
             kind="toggle", toggle="Swipe", tip="Swipe"),

        dict(id="show-Annotation", label="Annotation", icon="annotation", size="large",
                     kind="toggle", toggle="Annotation", tip="Annotation"),
    ],
}
