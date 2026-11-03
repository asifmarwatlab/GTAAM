"""How much of the layer is NoData, and where."""
from __future__ import annotations

import numpy as np


def run(data: np.ndarray) -> dict:
    holes = ~np.isfinite(data)
    count = int(holes.sum())
    total = int(data.size)
    return {
        "nodata_count": count,
        "total": total,
        "percent": round(100.0 * count / total, 4) if total else 0.0,
        "rows_affected": int(holes.any(axis=1).sum()),
        "columns_affected": int(holes.any(axis=0).sum()),
        "status": "clean" if count == 0 else "has_nodata",
    }
