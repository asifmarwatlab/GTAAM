"""TerrainApi - the one object the UI holds.

    api = TerrainApi()                                   # http://127.0.0.1:8000
    layer = api.file.add_raster(r"C:\\data\\dem.tif")
    result = api.analysis.slope(layer["id"])             # new layer + statistics
    png = api.file.map_image(result["layer"]["id"], ramp="slope")
"""
from __future__ import annotations

import httpx

from .endpoints.analysis import AnalysisApi
from .endpoints.editing import EditingApi
from .endpoints.file import FileApi
from .endpoints.jobs import JobsApi
from .endpoints.mosaic import MosaicApi
from .endpoints.tools import ToolsApi
from .endpoints.view import ViewApi
from .errors import ApiConnectionError
from .http import HttpClient


class TerrainApi:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", *, api_prefix: str = "/api/v1",
                 timeout: float = 120.0, client: httpx.Client | None = None):
        self._http = HttpClient(base_url, api_prefix, timeout, client)
        self.file = FileApi(self._http)              # File tab
        self.view = ViewApi(self._http)              # View tab
        self.analysis = AnalysisApi(self._http)      # Analysis tab
        self.tools = ToolsApi(self._http)            # Tools tab
        self.editing = EditingApi(self._http)        # Terrain Editing tab
        self.mosaic = MosaicApi(self._http)          # Terrain Mosaic tab
        self.jobs = JobsApi(self._http)

    @property
    def base_url(self) -> str:
        return self._http.base_url

    def health(self) -> dict:
        """{"status": "ok", "version": ..., "modules": [...]} - raises if the backend is down."""
        return self._http.get("/health")

    def is_alive(self) -> bool:
        try:
            return self.health().get("status") == "ok"
        except ApiConnectionError:
            return False
        except Exception:                                    # noqa: BLE001
            return False

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "TerrainApi":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
