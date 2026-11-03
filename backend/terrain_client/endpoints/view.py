from __future__ import annotations

from ..http import clean
from .base import Endpoints


class ViewApi(Endpoints):
    """View tab: Navigate, Panes, Appearance, Display."""

    # ---- Navigate ----
    def explore(self, mode: str = "explore") -> dict:
        """mode: explore | identify | measure | draw"""
        return self._h.post("/view/navigate/explore", json={"mode": mode})

    def full_extent(self) -> dict:
        return self._h.get("/view/navigate/full-extent")

    def zoom_in(self, factor: float = 2.0) -> dict:
        return self._h.post("/view/navigate/zoom-in", json={"factor": factor})

    def zoom_out(self, factor: float = 2.0) -> dict:
        return self._h.post("/view/navigate/zoom-out", json={"factor": factor})

    def zoom_to_layer(self, layer_id: str) -> dict:
        return self._h.get(f"/view/navigate/zoom-to-layer/{layer_id}")

    def update_viewport(self, center: tuple[float, float] | None = None,
                        scale: float | None = None) -> dict:
        return self._h.put("/view/navigate/viewport", json=clean({"center": center, "scale": scale}))

    # ---- Panes ----
    def panes(self) -> dict:
        return self._h.get("/view/panes")

    def set_pane(self, name: str, visible: bool) -> dict:
        """name: contents | statistics | pixel_inspector"""
        return self._h.put(f"/view/panes/{name}", json={"visible": visible})

    # ---- Appearance ----
    def appearance(self) -> dict:
        return self._h.get("/view/appearance")

    def update_appearance(self, *, north_arrow: bool | None = None, scale_bar: bool | None = None,
                          layer_label: bool | None = None, colour_ramp: str | None = None) -> dict:
        return self._h.put("/view/appearance", json=clean({
            "north_arrow": north_arrow, "scale_bar": scale_bar,
            "layer_label": layer_label, "colour_ramp": colour_ramp}))

    def colour_ramps(self) -> list[str]:
        return self._h.get("/view/appearance/colour-ramps")

    # ---- Display ----
    def display(self) -> dict:
        return self._h.get("/view/display")

    def update_display(self, *, regions: bool | None = None, reference_grid: bool | None = None,
                       annotation: bool | None = None) -> dict:
        return self._h.put("/view/display", json=clean({
            "regions": regions, "reference_grid": reference_grid, "annotation": annotation}))

    def hillshade_image(self, layer_id: str, azimuth: float = 315, altitude: float = 45,
                        z_factor: float = 1.0) -> bytes:
        return self._h.get(f"/view/display/hillshade/{layer_id}", expect="bytes",
                           params={"azimuth": azimuth, "altitude": altitude, "z_factor": z_factor})

    def slope_image(self, layer_id: str, ramp: str = "slope") -> bytes:
        return self._h.get(f"/view/display/slope/{layer_id}", expect="bytes", params={"ramp": ramp})

    def contours(self, layer_id: str, interval: float = 100.0, base: float = 0.0) -> dict:
        """Contour lines as GeoJSON (for drawing only; use analysis.contours to make a layer)."""
        return self._h.get(f"/view/display/contours/{layer_id}",
                           params={"interval": interval, "base": base})

    def reference_grid(self, layer_id: str, spacing: float) -> dict:
        return self._h.get(f"/view/display/reference-grid/{layer_id}", params={"spacing": spacing})

    def add_annotation(self, x: float, y: float, text: str) -> dict:
        return self._h.post("/view/display/annotations", json={"x": x, "y": y, "text": text})

    def remove_annotation(self, note_id: str) -> dict:
        return self._h.delete(f"/view/display/annotations/{note_id}")
