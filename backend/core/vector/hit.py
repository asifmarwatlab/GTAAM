"""Which feature of a GeoJSON collection lies under a point? (pure maths, no web, no files)

Used by the Identify tool. All numbers are in the same system as the coordinates
(the backend keeps vector files in lon/lat), and `tol` is in those units too.
"""
from __future__ import annotations

import numpy as np


def _crossings(ring: np.ndarray, x: float, y: float) -> int:
    """Edges of the ring to the right of the point (odd count = point is inside)."""
    xs, ys = ring[:, 0], ring[:, 1]
    x2, y2 = np.roll(xs, -1), np.roll(ys, -1)
    straddle = (ys > y) != (y2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_cross = (x2 - xs) * (y - ys) / (y2 - ys) + xs
    return int(np.count_nonzero(straddle & (x < x_cross)))


def _line_distance(line: np.ndarray, x: float, y: float) -> float:
    a, b = line[:-1], line[1:]
    ab = b - a
    ap = np.array([x, y]) - a
    t = np.clip((ap * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-18), 0, 1)
    proj = a + ab * t[:, None]
    return float(np.hypot(proj[:, 0] - x, proj[:, 1] - y).min())


def _arr(coords) -> np.ndarray:
    return np.asarray(coords, dtype=float)[:, :2]


def geometry_hit(geom: dict | None, x: float, y: float, tol: float) -> bool:
    if not geom or not geom.get("type"):
        return False
    t, c = geom["type"], geom.get("coordinates")
    if t == "GeometryCollection":
        return any(geometry_hit(g, x, y, tol) for g in geom.get("geometries", []))
    if not c:
        return False
    if t == "Point":
        return float(np.hypot(c[0] - x, c[1] - y)) <= tol
    if t == "MultiPoint":
        p = _arr(c)
        return bool(np.hypot(p[:, 0] - x, p[:, 1] - y).min() <= tol)
    if t == "LineString":
        return len(c) >= 2 and _line_distance(_arr(c), x, y) <= tol
    if t == "MultiLineString":
        return any(len(ln) >= 2 and _line_distance(_arr(ln), x, y) <= tol for ln in c)
    if t == "Polygon":
        return _polygon_hit(c, x, y)
    if t == "MultiPolygon":
        return any(_polygon_hit(poly, x, y) for poly in c)
    return False


def _polygon_hit(rings, x: float, y: float) -> bool:
    # outer ring and holes together: an odd number of crossings means "inside, not in a hole"
    return sum(_crossings(_arr(r), x, y) for r in rings if len(r) >= 3) % 2 == 1


def top_feature_at(features: list[dict], x: float, y: float, tol: float) -> int | None:
    """Number of the top-most feature (the last one drawn) under the point, or None."""
    for i in range(len(features) - 1, -1, -1):
        if geometry_hit(features[i].get("geometry"), x, y, tol):
            return i
    return None
