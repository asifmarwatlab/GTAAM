"""File tab - project, add data, export and workspace commands."""
from . import Add_data, Export, Project

TAB = "File"
GROUPS = [Project.GROUP, Add_data.GROUP, Export.GROUP]
