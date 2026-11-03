"""Distances along a line. Geographic coordinates use the haversine formula."""
from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_008.8


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def segment_length(p, q, geographic: bool) -> float:
    if geographic:
        return haversine(p[0], p[1], q[0], q[1])
    return math.hypot(q[0] - p[0], q[1] - p[1])


def path_length(points, geographic: bool) -> dict:
    if len(points) < 2:
        raise ValueError("Need at least two points.")
    segs = [segment_length(points[i], points[i + 1], geographic) for i in range(len(points) - 1)]
    return {"total": sum(segs), "segments": segs, "unit": "m"}
