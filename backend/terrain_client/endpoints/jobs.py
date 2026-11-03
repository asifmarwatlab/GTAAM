from __future__ import annotations

import time
from typing import Callable

from ..errors import ApiError
from .base import Endpoints


class JobsApi(Endpoints):
    """Background jobs (slow work started with background=True)."""

    def list(self) -> list[dict]:
        return self._h.get("/jobs")

    def get(self, job_id: str) -> dict:
        return self._h.get(f"/jobs/{job_id}")

    def wait(self, job_id: str, timeout: float = 300.0, poll: float = 0.25,
             on_progress: Callable[[float, str], None] | None = None) -> dict:
        """Block until the job finishes and return its result.

        Raises ApiError(code="job_failed") if it failed and TimeoutError if it takes too long.
        Call it from a worker thread (see terrain_client.qt.run_async), never the GUI thread.
        """
        deadline = time.monotonic() + timeout
        while True:
            job = self.get(job_id)
            if on_progress:
                on_progress(job["progress"], job["message"])
            if job["state"] == "done":
                return job["result"]
            if job["state"] == "failed":
                raise ApiError(500, "job_failed", job["error"] or "The job failed.")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Job {job_id} did not finish within {timeout:g} s.")
            time.sleep(poll)
