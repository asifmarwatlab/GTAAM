"""Analysis tab - measure, quality/statistics, surface analysis, derivatives."""
from . import Measure, Quality_and_Statistics, Terrain_Derivatives

TAB = "Analysis"
GROUPS = [
    Measure.GROUP,
    Quality_and_Statistics.GROUP,
    Terrain_Derivatives.GROUP,
]
