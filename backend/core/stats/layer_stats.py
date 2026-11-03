"""Minimum, maximum, mean and standard deviation of a layer (NaN ignored)."""
from __future__ import annotations

import numpy as np

from core.raster.utils import num


def compute(data: np.ndarray) -> dict:
    valid = data[np.isfinite(data)]
    total = int(data.size)
    base = {"count": int(valid.size), "nodata_count": total - int(valid.size), "total": total}
    if valid.size == 0:
        return {"min": None, "max": None, "mean": None, "std_dev": None, "median": None, **base}
    return {"min": num(valid.min()), "max": num(valid.max()), "mean": num(valid.mean()),
            "std_dev": num(valid.std()), "median": num(np.median(valid)), **base}
