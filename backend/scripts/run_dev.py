"""Start the API for development:  py scripts/run_dev.py   (from anywhere)"""
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True,
                reload_dirs=[str(ROOT)], reload_excludes=[".venv/*", "storage/*", "tests/*"])
