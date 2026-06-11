"""In-memory background job runner for long agent phases.

Agent phases (write/edit/validate…) call the LLM and take 30–90s, so they must
never run inline in a request. We run them on a daemon thread and expose status
for the UI to poll. Single-process, single-user — no external queue needed.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[], None], meta: Optional[dict] = None) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "kind": kind,
                "status": "running",
                "error": None,
                "started_at": _now(),
                "finished_at": None,
                **(meta or {}),
            }

        def run() -> None:
            try:
                fn()
                self._update(job_id, status="done")
            except Exception as e:  # noqa: BLE001 - surface any agent failure to the UI
                self._update(job_id, status="error", error=f"{type(e).__name__}: {e}")

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.update(fields)
                job["finished_at"] = _now()

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


# Process-wide singleton.
runner = JobRunner()
