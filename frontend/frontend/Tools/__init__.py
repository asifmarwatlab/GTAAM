"""Tools tab - data management, inspect and workspace tools."""
from . import data_management, workspace
from . import inspect as inspect_tools

TAB = "Tools"
GROUPS = [data_management.GROUP, inspect_tools.GROUP, workspace.GROUP]
