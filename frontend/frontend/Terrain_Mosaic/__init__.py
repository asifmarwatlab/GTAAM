"""Terrain Mosaic tab - input, overlap analysis, mosaic and output."""
from . import Input, Mosaic, Overlap_analysis, output

TAB = "Terrain Mosaic"
GROUPS = [Input.GROUP, Overlap_analysis.GROUP, Mosaic.GROUP, output.GROUP]
