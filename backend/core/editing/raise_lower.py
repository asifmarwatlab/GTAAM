"""Raise or lower the terrain inside a mask by a fixed amount (metres)."""
from __future__ import annotations

import numpy as np


def raise_lower(data: np.ndarray, mask: np.ndarray, amount: float) -> np.ndarray:
    out = data.copy()
    out[mask] += np.float32(amount)           # NaN + amount stays NaN
    return out
