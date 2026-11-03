"""Before / after comparison of an edit."""
from __future__ import annotations

import numpy as np

from core.raster.utils import num


def compare(before: np.ndarray, after: np.ndarray, cell_area_m2: float | None = None) -> dict:
    diff = after.astype(np.float64) - before.astype(np.float64)
    ok = np.isfinite(diff)
    changed = ok & (np.abs(diff) > 1e-6)
    d = diff[changed]
    out = {
        "changed_cells": int(changed.sum()),
        "mean_change": num(d.mean()) if d.size else 0.0,
        "max_raise": num(d.max()) if d.size and d.max() > 0 else 0.0,
        "max_lower": num(d.min()) if d.size and d.min() < 0 else 0.0,
        "rmse": num(np.sqrt(np.mean(diff[ok] ** 2))) if ok.any() else None,
    }
    if cell_area_m2 is not None:
        out["volume_change_m3"] = num(np.nansum(diff[ok]) * cell_area_m2)
    return out
