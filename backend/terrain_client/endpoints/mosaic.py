from __future__ import annotations

from ..http import clean
from .base import Endpoints


class MosaicApi(Endpoints):
    """Terrain Mosaic tab.

    Flow: select_dems -> difference_map / seamline -> set_blend_settings -> preview -> apply.
    """

    # ---- Input ----
    def select_dems(self, layer_ids: list[str]) -> dict:
        """Reply has `compatible` (same CRS and cell size) and `problem` if not."""
        return self._h.post("/terrain-mosaic/input/select-dems", json={"layer_ids": layer_ids})

    def selection(self) -> dict:
        return self._h.get("/terrain-mosaic/input/select-dems")

    # ---- Overlap Analysis (omit the ids to use the first two selected DEMs) ----
    def difference_map(self, layer_a: str | None = None, layer_b: str | None = None) -> dict:
        return self._h.post("/terrain-mosaic/overlap-analysis/difference-map",
                            json=clean({"layer_a": layer_a, "layer_b": layer_b}))

    def seamline(self, layer_a: str | None = None, layer_b: str | None = None) -> dict:
        return self._h.post("/terrain-mosaic/overlap-analysis/seamline",
                            json=clean({"layer_a": layer_a, "layer_b": layer_b}))

    # ---- Mosaic ----
    def blend_settings(self) -> dict:
        return self._h.get("/terrain-mosaic/mosaic/blend-settings")

    def set_blend_settings(self, method: str = "feather", feather_pixels: int = 20) -> dict:
        """method: feather | first | last | mean | min | max"""
        return self._h.put("/terrain-mosaic/mosaic/blend-settings",
                           json={"method": method, "feather_pixels": feather_pixels})

    def preview(self, background: bool = False) -> dict:
        """background=True returns {"job_id": ...}; then api.jobs.wait(job_id)."""
        return self._h.post("/terrain-mosaic/mosaic/preview", params={"background": background or None})

    def apply(self) -> dict:
        return self._h.post("/terrain-mosaic/mosaic/apply")

    # ---- Output ----
    def export_elevations(self, path: str) -> dict:
        return self._h.post("/terrain-mosaic/output/export-elevations", json={"path": path})
