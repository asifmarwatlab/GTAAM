"""Draw a raster as a PNG (own tiny encoder, so no Pillow needed)."""
from __future__ import annotations

import math
import struct
import zlib

import numpy as np

from core.raster.model import Raster

from .colour_ramp import apply_ramp


def encode_png(rgba: np.ndarray) -> bytes:
    h, w, _ = rgba.shape

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = np.concatenate([np.zeros((h, 1), dtype=np.uint8), rgba.reshape(h, w * 4)], axis=1)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6))
            + chunk(b"IEND", b""))


def render_png(raster: Raster, ramp: str = "terrain", vmin: float | None = None,
               vmax: float | None = None, max_pixels: int = 4_000_000) -> bytes:
    data = raster.data
    if data.size > max_pixels:                       # keep huge DEMs responsive
        step = math.ceil(math.sqrt(data.size / max_pixels))
        data = data[::step, ::step]
    return encode_png(apply_ramp(data, ramp, vmin, vmax))
