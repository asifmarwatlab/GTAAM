from __future__ import annotations

from ..http import clean
from .base import Endpoints

XY = tuple[float, float]


class AnalysisApi(Endpoints):
    """Analysis tab. Tools that make something return {"layer": {...}, "statistics": {...}}
    and the new layer appears in file.layers()."""

    # ---- Measure (points are in the layer's coordinate system) ----
    def distance(self, layer_id: str, points: list[XY]) -> dict:
        return self._h.post("/analysis/measure/distance", json={"layer_id": layer_id, "points": points})

    def area(self, layer_id: str, polygon: list[XY]) -> dict:
        return self._h.post("/analysis/measure/area", json={"layer_id": layer_id, "polygon": polygon})

    def elevation_profile(self, layer_id: str, line: list[XY], samples: int = 200) -> dict:
        return self._h.post("/analysis/measure/elevation-profile",
                            json={"layer_id": layer_id, "line": line, "samples": samples})

    # ---- Quality & Statistics ----
    def layer_statistics(self, layer_id: str) -> dict:
        return self._h.get(f"/analysis/quality-statistics/layer-statistics/{layer_id}")

    def histogram(self, layer_id: str, bins: int = 50) -> dict:
        return self._h.get(f"/analysis/quality-statistics/histogram/{layer_id}", params={"bins": bins})

    def nodata_check(self, layer_id: str) -> dict:
        return self._h.get(f"/analysis/quality-statistics/nodata-check/{layer_id}")

    def outlier_check(self, layer_id: str, method: str = "iqr", threshold: float | None = None) -> dict:
        """method: iqr | zscore"""
        return self._h.get(f"/analysis/quality-statistics/outlier-check/{layer_id}",
                           params={"method": method, "threshold": threshold})

    # ---- Surface Analysis ----
    def hillshade(self, layer_id: str, azimuth: float = 315, altitude: float = 45,
                  z_factor: float = 1.0) -> dict:
        return self._h.post("/analysis/surface-analysis/hillshade", json={
            "layer_id": layer_id, "azimuth": azimuth, "altitude": altitude, "z_factor": z_factor})

    def slope(self, layer_id: str, units: str = "degrees") -> dict:
        """units: degrees | percent"""
        return self._h.post("/analysis/surface-analysis/slope", json={"layer_id": layer_id, "units": units})

    def aspect(self, layer_id: str, flat_as_minus_one: bool = False) -> dict:
        return self._h.post("/analysis/surface-analysis/aspect",
                            json={"layer_id": layer_id, "flat_as_minus_one": flat_as_minus_one})

    def curvature(self, layer_id: str) -> dict:
        return self._h.post("/analysis/surface-analysis/curvature", json={"layer_id": layer_id})

    # ---- Terrain Derivatives ----
    def contours(self, layer_id: str, interval: float = 100.0, base: float = 0.0) -> dict:
        """Adds a vector layer; fetch its lines with file.layer_geojson(result["layer"]["id"])."""
        return self._h.post("/analysis/terrain-derivatives/contours",
                            json={"layer_id": layer_id, "interval": interval, "base": base})

    def roughness(self, layer_id: str) -> dict:
        return self._h.post("/analysis/terrain-derivatives/roughness", json={"layer_id": layer_id})

    def tpi(self, layer_id: str) -> dict:
        return self._h.post("/analysis/terrain-derivatives/tpi", json={"layer_id": layer_id})

    def ruggedness(self, layer_id: str) -> dict:
        return self._h.post("/analysis/terrain-derivatives/ruggedness", json={"layer_id": layer_id})
