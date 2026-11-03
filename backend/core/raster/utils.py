"""Small helpers so results are always valid JSON (NaN is not valid JSON)."""
from __future__ import annotations

import math

import numpy as np


def num(value) -> float | None:
    """float(value), or None when it is NaN/inf/None."""
    if value is None:
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def to_list(array) -> list:
    """numpy array -> plain list with NaN replaced by None."""
    a = np.asarray(array, dtype=float)
    return [None if not math.isfinite(v) else float(v) for v in a.ravel().tolist()]
