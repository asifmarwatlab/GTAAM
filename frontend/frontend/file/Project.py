"""File > Project group.

Ribbon spec keys: id, label, icon (see ui/panels/icon_generator.py), tip,
size (large|small), kind (action|panel|dialog|toggle|toast), action / fields.
"""
GROUP = {
    "label": "Project",
    "tools": [
        dict(id="new-project", label="New Project", icon="file_new", kind="action",
             action="new_project", tip="New Project"),

        dict(id="open-project", label="Open Project", icon="file_open", kind="action",
             action="open_project", tip="Open Project"),

        dict(id="save-project", label="Save", icon="save", kind="action",
             action="save_project", tip="Save project"),
             
        dict(id="save-project-as", label="Save As", icon="save_as",
             kind="action", action="save_project_as", tip="Save Project As"),
    ],
}
