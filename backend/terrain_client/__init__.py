"""Client for the Terrain Studio API. Needs only `httpx` (PyQt6 only for terrain_client.qt)."""
from .api import TerrainApi
from .errors import ApiConnectionError, ApiError, TerrainClientError

__all__ = ["TerrainApi", "ApiError", "ApiConnectionError", "TerrainClientError"]
__version__ = "1.0.0"
