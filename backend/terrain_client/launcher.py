"""Start the backend from the desktop app and stop it when the app closes.

    backend = BackendProcess(r"C:\\path\\to\\terrain_backend")
    api = TerrainApi(backend.start())          # picks a free port, waits until healthy
    ...
    backend.stop()                             # e.g. in closeEvent
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from .errors import TerrainClientError


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class BackendProcess:
    def __init__(self, backend_dir: str | Path, *, host: str = "127.0.0.1", port: int | None = None,
                 python: str | None = None, env: dict | None = None, startup_timeout: float = 30.0):
        self.backend_dir = Path(backend_dir)
        self.host, self.port = host, port
        self.python = python or sys.executable
        self.env = env
        self.startup_timeout = startup_timeout
        self._proc: subprocess.Popen | None = None
        self._log = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> str:
        """Launch uvicorn, wait until /health answers, return the base URL."""
        if self.is_running():
            return self.base_url
        if not (self.backend_dir / "main.py").is_file():
            raise TerrainClientError(f"Not a backend folder (main.py missing): {self.backend_dir}")
        self.port = self.port or free_port()
        self._log = tempfile.NamedTemporaryFile("w+", suffix=".log", prefix="terrain_backend_", delete=False)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)          # no console window on Windows
        self._proc = subprocess.Popen(
            [self.python, "-m", "uvicorn", "main:app", "--host", self.host,
             "--port", str(self.port), "--log-level", "warning"],
            cwd=self.backend_dir, stdout=self._log, stderr=subprocess.STDOUT,
            env={**os.environ, **(self.env or {})}, creationflags=flags)
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise TerrainClientError(f"The backend exited during startup.\n{self._log_tail()}")
            try:
                if httpx.get(f"{self.base_url}/health", timeout=1.0).status_code == 200:
                    return self.base_url
            except httpx.HTTPError:
                time.sleep(0.2)
        self.stop()
        raise TerrainClientError(f"The backend did not start within {self.startup_timeout:g} s.\n{self._log_tail()}")

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        if self._log is not None:
            self._log.close()

    def _log_tail(self, lines: int = 15) -> str:
        try:
            self._log.flush()
            return "\n".join(Path(self._log.name).read_text(errors="replace").splitlines()[-lines:])
        except Exception:                                            # noqa: BLE001
            return ""

    def __enter__(self) -> str:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
