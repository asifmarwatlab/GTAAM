"""Difference map: A minus B over the area where two DEMs overlap."""
from __future__ import annotations

import numpy as np

from core.raster.model import Raster
from core.raster.utils import num

from .grid import check_compatible, overlap_bounds, window


def difference_map(a: Raster, b: Raster) -> tuple[Raster, dict]:
    check_compatible([a, b])
    ov = overlap_bounds(a, b)
    if ov is None:
        raise ValueError("The two DEMs do not overlap.")
    wa, wb = window(a, ov), window(b, ov)
    h, w = min(wa.shape[0], wb.shape[0]), min(wa.shape[1], wb.shape[1])
    diff = (wa[:h, :w].astype(np.float64) - wb[:h, :w].astype(np.float64)).astype(np.float32)
    transform = (a.pixel_w, 0.0, ov[0], 0.0, -a.pixel_h, ov[3])
    raster = Raster(diff, transform, a.crs, a.nodata)
    ok = np.isfinite(diff)
    stats = {
        "overlap_bounds": list(ov), "overlap_cells": int(ok.sum()),
        "bias": num(diff[ok].mean()) if ok.any() else None,
        "mae": num(np.abs(diff[ok]).mean()) if ok.any() else None,
        "rmse": num(np.sqrt((diff[ok].astype(np.float64) ** 2).mean())) if ok.any() else None,
        "max_abs": num(np.abs(diff[ok]).max()) if ok.any() else None,
    }
    return raster, stats
