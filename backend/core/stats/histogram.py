"""Value distribution."""
from __future__ import annotations

import numpy as np


def compute(data: np.ndarray, bins: int = 50, value_range: tuple[float, float] | None = None) -> dict:
    if bins < 1:
        raise ValueError("bins must be at least 1.")
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        return {"bins": bins, "bin_edges": [], "counts": [], "pixels": 0}
    counts, edges = np.histogram(valid, bins=bins, range=value_range)
    return {"bins": bins, "bin_edges": [float(e) for e in edges],
            "counts": [int(c) for c in counts], "pixels": int(valid.size)}
