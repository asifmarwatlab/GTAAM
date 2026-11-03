"""Find suspicious extreme values (spikes and pits)."""
from __future__ import annotations

import numpy as np

from core.raster.utils import num

METHODS = ("iqr", "zscore")


def bounds(data: np.ndarray, method: str = "iqr", threshold: float | None = None):
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        raise ValueError("The layer has no valid cells.")
    if method == "iqr":
        k = 1.5 if threshold is None else threshold
        q1, q3 = np.percentile(valid, [25, 75])
        spread = q3 - q1
        return q1 - k * spread, q3 + k * spread, k
    k = 3.0 if threshold is None else threshold
    mean, std = valid.mean(), valid.std()
    return mean - k * std, mean + k * std, k


def outlier_mask(data: np.ndarray, method: str = "iqr", threshold: float | None = None) -> np.ndarray:
    lo, hi, _ = bounds(data, method, threshold)
    with np.errstate(invalid="ignore"):
        return np.isfinite(data) & ((data < lo) | (data > hi))


def run(data: np.ndarray, method: str = "iqr", threshold: float | None = None) -> dict:
    lo, hi, k = bounds(data, method, threshold)
    mask = outlier_mask(data, method, threshold)
    valid = int(np.isfinite(data).sum())
    count = int(mask.sum())
    return {"method": method, "threshold": k, "lower_bound": num(lo), "upper_bound": num(hi),
            "outlier_count": count, "percent": round(100.0 * count / valid, 4) if valid else 0.0,
            "lowest_outlier": num(data[mask].min()) if count else None,
            "highest_outlier": num(data[mask].max()) if count else None}
