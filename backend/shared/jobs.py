"""Background jobs for slow work (mosaic, reproject...). The UI polls /jobs/{id}.

Usage inside a service:
    def work(report):                 # report(progress 0..1, message)
        report(0.1, "reading")
        ...
        return {"done": True}         # must be JSON-serialisable
    job_id = jobs.submit("mosaic preview", work)
"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from shared.errors import NotFound


@dataclass
class Job:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    state: str = "pending"            # pending | running | done | failed
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    created: float = field(default_factory=time.time)
    finished: float | None = None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "state": self.state,
                "progress": round(self.progress, 3), "message": self.message,
                "result": self.result, "error": self.error}


class JobManager:
    def __init__(self, workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, fn: Callable[..., Any], *args, **kwargs) -> str:
        job = Job(name=name)
        with self._lock:
            self._jobs[job.id] = job

        def report(progress: float, message: str = "") -> None:
            job.progress, job.message = max(0.0, min(1.0, progress)), message

        def run() -> None:
            job.state = "running"
            try:
                job.result = fn(report, *args, **kwargs)
                job.progress, job.state = 1.0, "done"
            except Exception as exc:                       # noqa: BLE001 - report any failure
                job.error, job.state = str(exc), "failed"
            finally:
                job.finished = time.time()

        self._pool.submit(run)
        return job.id

    def get(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise NotFound(f"Job '{job_id}' does not exist.", code="job_not_found")

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)


jobs = JobManager()
