"""Polygon area. Geographic coordinates are flattened locally to metres first."""
from __future__ import annotations

import math

from core.raster.crs import M_PER_DEG_LAT, M_PER_DEG_LON_EQ


def _shoelace(pts) -> float:
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def polygon_area(polygon, geographic: bool) -> dict:
    if len(polygon) < 3:
        raise ValueError("A polygon needs at least three points.")
    if geographic:
        lon0 = sum(p[0] for p in polygon) / len(polygon)
        lat0 = sum(p[1] for p in polygon) / len(polygon)
        kx = M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
        pts = [((x - lon0) * kx, (y - lat0) * M_PER_DEG_LAT) for x, y in polygon]
    else:
        pts = [tuple(p) for p in polygon]
    m2 = _shoelace(pts)
    return {"area_m2": m2, "area_km2": m2 / 1e6, "area_ha": m2 / 1e4}
