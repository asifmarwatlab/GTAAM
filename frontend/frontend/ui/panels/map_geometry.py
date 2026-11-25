"""Where each raster sits on the map canvas. No Qt in here, so it can be tested on its own.

The canvas counts in "cells of the reference raster" (the first raster on the map): the reference raster
is drawn at (0, 0) and every cell of it is one unit. Any other raster is placed by its real position:
its four corners are moved into the reference raster's coordinate system and then turned into those cells.

A placement is six numbers (a, b, c, d, e, f). A pixel (px, py) of the layer's picture lands on the canvas at
    x = a * px + c * py + e
    y = b * px + d * py + f
For two layers in the same coordinate system this is exact. For layers in different systems (degrees and UTM)
a straight-edged picture is fitted to a grid of points. Over a DEM tile the leftover error is a fraction of a cell.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

Affine = tuple[float, float, float, float, float, float]
IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def same_crs(a: str | None, b: str | None) -> bool:
    return (a or "").replace(" ", "").upper() == (b or "").replace(" ", "").upper()


@lru_cache(maxsize=32)
def _transformer(src: str, dst: str):
    try:
        from pyproj import Transformer
        return Transformer.from_crs(src, dst, always_xy=True).transform
    except ImportError:                                   # rasterio can do the same job
        from rasterio.warp import transform
        return lambda xs, ys: transform(src, dst, list(np.ravel(xs)), list(np.ravel(ys)))


def transform_xy(src: str, dst: str, xs, ys) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if same_crs(src, dst):
        return xs, ys
    ox, oy = _transformer(src, dst)(xs.ravel(), ys.ravel())
    return np.asarray(ox, float).reshape(xs.shape), np.asarray(oy, float).reshape(ys.shape)


def _valid_bounds(b) -> bool:
    return b is not None and len(b) == 4 and b[2] > b[0] and b[3] > b[1] and all(np.isfinite(b))


def placement(ref_bounds, ref_size, ref_crs, bounds, size, crs, n: int = 5) -> Affine | None:
    """Placement of a layer on the canvas. Sizes are (width, height) of the pictures in pixels.
    None means it cannot be worked out (no coordinate system, no bounds, or outside the projection)."""
    if not (_valid_bounds(ref_bounds) and _valid_bounds(bounds) and ref_crs and crs):
        return None
    rw, rh = ref_size
    w, h = size
    if min(rw, rh, w, h) <= 0:
        return None
    px, py = np.meshgrid(np.linspace(0.0, w, n), np.linspace(0.0, h, n))
    x = bounds[0] + px / w * (bounds[2] - bounds[0])
    y = bounds[3] - py / h * (bounds[3] - bounds[1])
    try:
        x, y = transform_xy(crs, ref_crs, x, y)
    except Exception:
        return None
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        return None
    cx = (x - ref_bounds[0]) / (ref_bounds[2] - ref_bounds[0]) * rw       # reference cells
    cy = (ref_bounds[3] - y) / (ref_bounds[3] - ref_bounds[1]) * rh
    design = np.column_stack([px.ravel(), py.ravel(), np.ones(px.size)])
    (a, b), (c, d), (e, f) = np.linalg.lstsq(design, np.column_stack([cx.ravel(), cy.ravel()]), rcond=None)[0]
    return float(a), float(b), float(c), float(d), float(e), float(f)


def apply(t: Affine, px, py):
    a, b, c, d, e, f = t
    px, py = np.asarray(px, float), np.asarray(py, float)
    return a * px + c * py + e, b * px + d * py + f


def invert(t: Affine) -> Affine | None:
    a, b, c, d, e, f = t
    det = a * d - b * c
    if abs(det) < 1e-18:
        return None
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f)


def to_layer_pixel(t: Affine, x: float, y: float) -> tuple[float, float] | None:
    """The pixel of the layer's picture that lies under canvas position (x, y)."""
    inv = invert(t)
    if inv is None:
        return None
    px, py = apply(inv, x, y)
    return float(px), float(py)


def canvas_box(t: Affine, size) -> tuple[float, float, float, float]:
    """Smallest box (x0, y0, x1, y1) on the canvas that holds the whole picture."""
    w, h = size
    xs, ys = apply(t, np.array([0.0, w, 0.0, w]), np.array([0.0, 0.0, h, h]))
    return float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
