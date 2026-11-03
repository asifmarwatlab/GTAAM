from __future__ import annotations

from ..http import clean
from .base import Endpoints

XY = tuple[float, float]


class EditingApi(Endpoints):
    """Terrain Editing tab.

    Flow: draw_region -> raise_lower / smooth / flatten / fill_sinks (queued) ->
    preview -> compare -> apply (new "(edited)" layer) or discard.
    Leave region_ids out to use the currently selected regions.
    """

    # ---- Selection ----
    def draw_region(self, layer_id: str, polygon: list[XY], name: str | None = None) -> dict:
        return self._h.post("/terrain-editing/selection/draw-region",
                            json=clean({"layer_id": layer_id, "polygon": polygon, "name": name}))

    def regions(self, layer_id: str) -> dict:
        return self._h.get(f"/terrain-editing/selection/regions/{layer_id}")

    def select_region(self, layer_id: str, region_ids: list[str]) -> dict:
        return self._h.post("/terrain-editing/selection/select-region",
                            json={"layer_id": layer_id, "region_ids": region_ids})

    def delete_selected(self, layer_id: str) -> dict:
        return self._h.post("/terrain-editing/selection/delete-selected", json={"layer_id": layer_id})

    def clear_all(self, layer_id: str) -> dict:
        return self._h.post("/terrain-editing/selection/clear-all", json={"layer_id": layer_id})

    # ---- Modify Terrain (queues an edit; nothing changes until apply) ----
    def raise_lower(self, layer_id: str, amount: float, region_ids: list[str] | None = None) -> dict:
        """amount in metres: positive raises, negative lowers."""
        return self._h.post("/terrain-editing/modify-terrain/raise-lower",
                            json=clean({"layer_id": layer_id, "amount": amount, "region_ids": region_ids}))

    def smooth(self, layer_id: str, iterations: int = 1, region_ids: list[str] | None = None) -> dict:
        return self._h.post("/terrain-editing/modify-terrain/smooth",
                            json=clean({"layer_id": layer_id, "iterations": iterations, "region_ids": region_ids}))

    def flatten(self, layer_id: str, elevation: float | None = None,
                region_ids: list[str] | None = None) -> dict:
        """elevation=None flattens to the area's mean."""
        return self._h.post("/terrain-editing/modify-terrain/flatten",
                            json=clean({"layer_id": layer_id, "elevation": elevation, "region_ids": region_ids}))

    def fill_sinks(self, layer_id: str, region_ids: list[str] | None = None) -> dict:
        return self._h.post("/terrain-editing/modify-terrain/fill-sinks",
                            json=clean({"layer_id": layer_id, "region_ids": region_ids}))

    # ---- Review ----
    def pending(self, layer_id: str) -> dict:
        return self._h.get(f"/terrain-editing/review/pending/{layer_id}")

    def preview(self, layer_id: str) -> dict:
        return self._h.post("/terrain-editing/review/preview", json={"layer_id": layer_id})

    def compare(self, layer_id: str) -> dict:
        return self._h.post("/terrain-editing/review/compare", json={"layer_id": layer_id})

    def discard(self, layer_id: str) -> dict:
        return self._h.post("/terrain-editing/review/discard", json={"layer_id": layer_id})

    # ---- Output ----
    def apply(self, layer_id: str) -> dict:
        """Creates a new "(edited)" layer; the original is untouched."""
        return self._h.post("/terrain-editing/output/apply", json={"layer_id": layer_id})

    def export_edited_dem(self, layer_id: str, path: str) -> dict:
        return self._h.post("/terrain-editing/output/export-edited-dem",
                            json={"layer_id": layer_id, "path": path})
