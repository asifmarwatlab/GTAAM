"""3x3 neighbourhood helper shared by terrain, editing and nodata code."""
from __future__ import annotations

import numpy as np


def shifted(a: np.ndarray, mode: str = "edge", **pad_kw) -> dict[str, np.ndarray]:
    """The 3x3 neighbourhood of every cell, as nine same-shaped arrays.

        nw n ne
        w  c e        e.g. out["n"][i, j] is the cell just north of a[i, j]
        sw s se

    Edges are padded by repeating the border cells (mode="edge").
    """
    h, w = a.shape
    p = np.pad(a, 1, mode=mode, **pad_kw)
    return {
        "nw": p[0:h, 0:w], "n": p[0:h, 1:w + 1], "ne": p[0:h, 2:w + 2],
        "w": p[1:h + 1, 0:w], "c": a, "e": p[1:h + 1, 2:w + 2],
        "sw": p[2:h + 2, 0:w], "s": p[2:h + 2, 1:w + 1], "se": p[2:h + 2, 2:w + 2],
    }


def bbox_of_mask(mask: np.ndarray, pad: int = 0) -> tuple[int, int, int, int] | None:
    """(row0, row1, col0, col1) of the True area (padded, clipped), or None if empty."""
    if not mask.any():
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    h, w = mask.shape
    return (max(rows[0] - pad, 0), min(rows[-1] + 1 + pad, h),
            max(cols[0] - pad, 0), min(cols[-1] + 1 + pad, w))
