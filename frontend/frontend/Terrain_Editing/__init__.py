"""Terrain Editing tab - selection, modify terrain, review and output."""
from . import modify_terrain, output, review, selection

TAB = "Terrain Editing"
GROUPS = [selection.GROUP, modify_terrain.GROUP, review.GROUP, output.GROUP]
