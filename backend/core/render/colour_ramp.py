"""Colour ramps: turn numbers into RGBA pixels."""
from __future__ import annotations

import numpy as np

RAMPS: dict[str, list[tuple[float, tuple[int, int, int]]]] = {
    "terrain": [(0.0, (38, 115, 76)), (0.25, (160, 190, 110)), (0.5, (235, 220, 150)),
                (0.75, (170, 120, 80)), (1.0, (250, 250, 250))],
    "greys": [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
    "viridis": [(0.0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 144, 140)),
                (0.75, (93, 201, 99)), (1.0, (253, 231, 37))],
    "magma": [(0.0, (0, 0, 4)), (0.25, (81, 18, 124)), (0.5, (183, 55, 121)),
              (0.75, (252, 137, 97)), (1.0, (252, 253, 191))],
    "slope": [(0.0, (255, 255, 255)), (0.5, (253, 174, 97)), (1.0, (165, 0, 38))],
    "diverging": [(0.0, (49, 54, 149)), (0.5, (255, 255, 191)), (1.0, (165, 0, 38))],
}


def apply_ramp(data: np.ndarray, ramp: str = "terrain", vmin: float | None = None,
               vmax: float | None = None) -> np.ndarray:
    """Returns uint8 array (h, w, 4). NaN cells are fully transparent."""
    if ramp not in RAMPS:
        raise ValueError(f"Unknown colour ramp '{ramp}'. Choose from {sorted(RAMPS)}.")
    ok = np.isfinite(data)
    if not ok.any():
        return np.zeros((*data.shape, 4), dtype=np.uint8)
    lo = float(np.min(data[ok])) if vmin is None else vmin
    hi = float(np.max(data[ok])) if vmax is None else vmax
    t = np.clip((data - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros(data.shape)
    t = np.where(ok, t, 0)
    pos = [p for p, _ in RAMPS[ramp]]
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    for ch in range(3):
        rgba[..., ch] = np.interp(t, pos, [c[ch] for _, c in RAMPS[ramp]]).astype(np.uint8)
    rgba[..., 3] = np.where(ok, 255, 0)
    return rgba
