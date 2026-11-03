"""The only place that talks HTTP. Everything else calls HttpClient.request()."""
from __future__ import annotations

from typing import Any

import httpx

from .errors import ApiConnectionError, ApiError


def clean(data: dict) -> dict:
    """Drop None values so optional arguments are simply left out of the request."""
    return {k: v for k, v in data.items() if v is not None}


class HttpClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", api_prefix: str = "/api/v1",
                 timeout: float = 120.0, client: httpx.Client | None = None):
        self.api_prefix = api_prefix.rstrip("/")
        # `client` lets tests (or a custom setup) supply their own httpx.Client
        self.client = client or httpx.Client(base_url=base_url,
                                             timeout=httpx.Timeout(timeout, connect=5.0))

    @property
    def base_url(self) -> str:
        return str(self.client.base_url).rstrip("/")

    def request(self, method: str, path: str, *, json: Any = None, params: dict | None = None,
                expect: str = "json", prefix: bool = True) -> Any:
        """expect: "json" -> dict/list, "bytes" -> raw bytes (PNG), "text" -> str (CSV)."""
        url = (self.api_prefix if prefix else "") + path
        try:
            resp = self.client.request(method, url, json=json, params=clean(params or {}) or None)
        except httpx.TimeoutException as exc:
            raise ApiConnectionError(f"The backend at {self.base_url} did not answer in time.") from exc
        except httpx.HTTPError as exc:
            raise ApiConnectionError(
                f"Cannot reach the backend at {self.base_url}. Is it running?") from exc
        if resp.status_code >= 400:
            raise self._to_error(resp)
        if expect == "bytes":
            return resp.content
        if expect == "text":
            return resp.text
        return resp.json() if resp.content else {}

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def patch(self, path, **kw):
        return self.request("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _to_error(resp: httpx.Response) -> ApiError:
        try:
            body = resp.json()
        except ValueError:
            return ApiError(resp.status_code, "http_error", resp.text or resp.reason_phrase)
        if isinstance(body, dict) and "error" in body:                     # our own errors
            return ApiError(resp.status_code, body["error"], body.get("message", ""))
        if isinstance(body, dict) and isinstance(body.get("detail"), list):  # request validation
            parts = []
            for item in body["detail"]:
                where = ".".join(str(p) for p in item.get("loc", []) if p not in ("body", "query", "path"))
                parts.append(f"{where}: {item.get('msg', 'invalid')}" if where else item.get("msg", "invalid"))
            return ApiError(resp.status_code, "validation_error", "; ".join(parts) or "Invalid request.")
        if isinstance(body, dict) and "detail" in body:
            return ApiError(resp.status_code, "http_error", str(body["detail"]))
        return ApiError(resp.status_code, "http_error", str(body))
