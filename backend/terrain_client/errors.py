"""Errors the UI can catch. Everything the client raises derives from TerrainClientError."""
from __future__ import annotations


class TerrainClientError(Exception):
    """Base class: catch this to catch everything."""


class ApiError(TerrainClientError):
    """The backend answered with an error (4xx / 5xx).

    status   HTTP status, e.g. 404
    code     short machine name, e.g. "layer_not_found", "invalid_value", "validation_error"
    message  sentence you can show to the user
    """

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"ApiError(status={self.status}, code={self.code!r}, message={self.message!r})"


class ApiConnectionError(TerrainClientError):
    """The backend could not be reached (not running, wrong port, timed out)."""
