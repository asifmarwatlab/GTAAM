"""Seamline: the cheapest path through the overlap, where the two DEMs agree best."""
from __future__ import annotations

import numpy as np

from core.raster.model import Raster

from .difference import difference_map


def _cheapest_path(cost: np.ndarray) -> np.ndarray:
    """Top-to-bottom path (one column per row) with the lowest total cost, moving at most
    one column sideways per row. Returns the column index of every row."""
    n, m = cost.shape
    acc = cost.astype(np.float64).copy()
    back = np.zeros((n, m), dtype=np.int8)
    cols = np.arange(m)
    for i in range(1, n):
        prev = acc[i - 1]
        stack = np.vstack([np.r_[np.inf, prev[:-1]], prev, np.r_[prev[1:], np.inf]])
        pick = stack.argmin(axis=0)
        acc[i] += stack[pick, cols]
        back[i] = pick - 1
    path = np.zeros(n, dtype=int)
    j = int(acc[-1].argmin())
    for i in range(n - 1, -1, -1):
        path[i] = j
        j += int(back[i, j])
    return path


def min_difference_seamline(a: Raster, b: Raster) -> dict:
    diff, stats = difference_map(a, b)
    cost = np.abs(diff.data).astype(np.float64)
    fill = np.nanmean(cost) if np.isfinite(cost).any() else 0.0
    cost = np.where(np.isfinite(cost), cost, fill)
    xs, ys = diff.x_coords(), diff.y_coords()
    if diff.width >= diff.height:                 # wide overlap -> seam runs left to right
        rows = _cheapest_path(cost.T)
        coords = [[float(xs[i]), float(ys[r])] for i, r in enumerate(rows)]
    else:                                         # tall overlap -> seam runs top to bottom
        cols = _cheapest_path(cost)
        coords = [[float(xs[c]), float(ys[i])] for i, c in enumerate(cols)]
    return {"type": "Feature",
            "properties": {"method": "min_difference", "overlap_cells": stats["overlap_cells"]},
            "geometry": {"type": "LineString", "coordinates": coords}}
