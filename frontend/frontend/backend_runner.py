import atexit
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
# Which backend to run, first match wins:
#   1. the AGTAAM_BACKEND_DIR environment variable
#   2. a one-line file "backend_dir.txt" next to this script (personal, not committed)
#   3. a "backend" folder next to the frontend repo folder
def _backend_dir() -> Path:
    env = os.environ.get("AGTAAM_BACKEND_DIR")
    if env:
        return Path(env)
    cfg = ROOT / "backend_dir.txt"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8").strip()
        if text and Path(text).is_dir():
            return Path(text)
    return ROOT.parent.parent / "backend"


BACKEND_DIR = _backend_dir()
APP = "main:app"                                  # backend/main.py ka `app`
HOST, PORT = "127.0.0.1", 8765
BASE_URL = f"http://{HOST}:{PORT}"
API_PREFIX = "/api/v1"                            # config.py ke settings.api_prefix jaisa
LOG_FILE = ROOT / "backend.log"                   # backend ka output yahan likha jata hai

_proc: subprocess.Popen | None = None


def _healthy() -> bool:
    try:
        return httpx.get(BASE_URL + "/health", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


def _backend_python() -> str:
    """The backend's own virtual environment (BACKEND_DIR/.venv) if it has one, because that
    is where its packages (fiona, rasterio ...) are installed. Otherwise the GUI's Python."""
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        cand = os.path.join(str(BACKEND_DIR), ".venv", *rel)
        if os.path.isfile(cand):
            return cand
    return sys.executable


def launch_backend() -> None:
    """Start the backend in the background and return immediately."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        return                                    # already starting / running
    if _healthy():
        return                                    # someone started it already
    log = open(LOG_FILE, "ab")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    _proc = subprocess.Popen(
        [_backend_python(), "-m", "uvicorn", APP, "--host", HOST, "--port", str(PORT)],
        cwd=BACKEND_DIR, stdout=log, stderr=log, creationflags=flags)
    atexit.register(stop_backend)


def wait_until_ready(timeout: float = 40.0) -> None:
    """Block until /health answers. Starts the backend if it is not running."""
    if not _healthy():
        launch_backend()
    t0 = time.time()
    while time.time() - t0 < timeout:
        if _healthy():
            return
        if _proc is not None and _proc.poll() is not None:
            raise RuntimeError(f"Backend stopped while starting. See {LOG_FILE}")
        time.sleep(0.3)
    raise RuntimeError(f"Backend did not start in {timeout:.0f}s. See {LOG_FILE}")


def stop_backend() -> None:
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(5)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None