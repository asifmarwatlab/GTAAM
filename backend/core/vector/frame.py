"""Shapes of a vector layer, ready to draw on a map picture. (pure maths, no web, no files)

A window draws on a grid of "cells": for a raster that is the pixels of the picture it shows.
This turns lon/lat or map coordinates into those cells, so the window does no geography.
"""
from __future__ import annotations

import numpy as np


def _arr(coords) -> np.ndarray:
    return np.asarray(coords, dtype=float)[:, :2]


def _parts(geom: dict) -> list[tuple[str, list[np.ndarray]]]:
    t, c = geom.get("type"), geom.get("coordinates")
    if not t or c is None:
        return []
    if t == "GeometryCollection":
        return [p for g in geom.get("geometries", []) for p in _parts(g)]
    if t == "Point":
        return [("pt", [_arr([c])])]
    if t == "MultiPoint":
        return [("pt", [_arr(c)])] if c else []
    if t == "LineString":
        return [("line", [_arr(c)])] if len(c) >= 2 else []
    if t == "MultiLineString":
        return [("line", [_arr(p) for p in c if len(p) >= 2])]
    if t == "Polygon":
        return [("poly", [_arr(r) for r in c if len(r)])]
    if t == "MultiPolygon":
        return [("poly", [_arr(r) for r in poly if len(r)]) for poly in c]
    return []


def _round(a: np.ndarray) -> list[list[float]]:
    return np.round(a, 2).tolist()


def to_cells(geojson: dict, *, bounds=None, width: int, height: int) -> dict:
    """Shapes in cell coordinates.

    bounds = (min_x, min_y, max_x, max_y) of a raster picture that is `width` x `height` cells:
             the shapes are lined up with that picture (geojson must be in the raster's system).
    bounds = None: nothing to line up with, so the data is fitted into a width x height window.
    """
    raw = [[p for g in [(f.get("geometry") or {})] for p in _parts(g)] for f in geojson.get("features", [])]
    allp = [a for parts in raw for _, arrs in parts for a in arrs if len(a)]
    out = {"total": len(raw), "view": None, "framed_on": "raster" if bounds else "own", "features": []}
    if not allp:
        out["features"] = [{"polys": [], "lines": [], "pts": [], "anchor": None, "bbox": None} for _ in raw]
        return out
    everything = np.vstack(allp)
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        sx = width / ((max_x - min_x) or 1.0)
        sy = height / ((max_y - min_y) or 1.0)

        def cells(a):
            return np.column_stack(((a[:, 0] - min_x) * sx, (max_y - a[:, 1]) * sy))
    else:
        gx0, gy0 = everything.min(axis=0)
        gx1, gy1 = everything.max(axis=0)
        kx = float(np.cos(np.radians((gy0 + gy1) / 2))) if abs(gy0) < 90 and abs(gx1) <= 360 else 1.0
        k = min(width / max((gx1 - gx0) * kx, 1e-12), height / max(gy1 - gy0, 1e-12))

        def cells(a):
            return np.column_stack(((a[:, 0] - gx0) * kx * k, (gy1 - a[:, 1]) * k))
    xs, ys = [], []
    for parts in raw:
        feat = {"polys": [], "lines": [], "pts": [], "anchor": None, "bbox": None}
        for kind, arrs in parts:
            cs = [cells(a) for a in arrs if len(a)]
            if kind == "pt":
                feat["pts"] += _round(np.vstack(cs)) if cs else []
            elif kind == "line":
                feat["lines"] += [_round(c) for c in cs]
            elif cs:
                feat["polys"].append([_round(c) for c in cs])
        every = [np.asarray(r) for poly in feat["polys"] for r in poly] + [np.asarray(l) for l in feat["lines"]]
        if feat["pts"]:
            every.append(np.asarray(feat["pts"]))
        if every:
            m = np.vstack(every)
            x0, y0, x1, y1 = m[:, 0].min(), m[:, 1].min(), m[:, 0].max(), m[:, 1].max()
            feat["bbox"] = [round(float(v), 2) for v in (x0, y0, x1, y1)]
            feat["anchor"] = [round(float((x0 + x1) / 2), 2), round(float((y0 + y1) / 2), 2)]
            xs += [x0, x1]
            ys += [y0, y1]
        out["features"].append(feat)
    out["view"] = [round(float(min(xs)), 2), round(float(min(ys)), 2),
                   round(float(max(xs)), 2), round(float(max(ys)), 2)]
    return out
