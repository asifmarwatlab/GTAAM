from __future__ import annotations

from ..http import clean
from .base import Endpoints


def _bbox(bounds) -> dict:
    """Accepts (min_x, min_y, max_x, max_y) or a dict with those keys."""
    if isinstance(bounds, dict):
        return bounds
    min_x, min_y, max_x, max_y = bounds
    return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}


class ToolsApi(Endpoints):
    """Tools tab: Data Management, Inspect, Workspace."""

    # ---- Data Management (each creates a new layer) ----
    def clip(self, layer_id: str, bounds) -> dict:
        return self._h.post("/tools/data-management/clip",
                            json={"layer_id": layer_id, "bounds": _bbox(bounds)})

    def resample(self, layer_id: str, cell_size: float, method: str = "bilinear") -> dict:
        """cell_size is in the layer's own units (degrees for lat/lon, metres for UTM)."""
        return self._h.post("/tools/data-management/resample",
                            json={"layer_id": layer_id, "cell_size": cell_size, "method": method})

    def reproject(self, layer_id: str, epsg: int, method: str = "bilinear") -> dict:
        return self._h.post("/tools/data-management/reproject",
                            json={"layer_id": layer_id, "epsg": epsg, "method": method})

    def fill_nodata(self, layer_id: str, max_iterations: int = 50) -> dict:
        return self._h.post("/tools/data-management/fill-nodata",
                            json={"layer_id": layer_id, "max_iterations": max_iterations})

    # ---- Inspect ----
    def identify(self, layer_id: str, x: float, y: float) -> dict:
        return self._h.post("/tools/inspect/identify", json={"layer_id": layer_id, "x": x, "y": y})

    def pixel(self, layer_id: str, x: float, y: float) -> dict:
        """Same answer as identify; use it for the live Pixel Inspector while the mouse moves."""
        return self._h.get(f"/tools/inspect/pixel/{layer_id}", params={"x": x, "y": y})

    def properties(self, layer_id: str) -> dict:
        """Feeds the Raster Properties panel."""
        return self._h.get(f"/tools/inspect/properties/{layer_id}")

    def metadata(self, layer_id: str) -> dict:
        return self._h.get(f"/tools/inspect/metadata/{layer_id}")

    # ---- Workspace ----
    def options(self) -> dict:
        return self._h.get("/tools/workspace/options")

    def update_options(self, *, units: str | None = None, decimals: int | None = None,
                       default_ramp: str | None = None) -> dict:
        return self._h.put("/tools/workspace/options",
                           json=clean({"units": units, "decimals": decimals, "default_ramp": default_ramp}))

    def shortcuts(self) -> list[dict]:
        return self._h.get("/tools/workspace/shortcuts")

    def about(self) -> dict:
        return self._h.get("/tools/workspace/about")
