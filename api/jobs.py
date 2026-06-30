"""In-memory background job runner for long agent phases.

Agent phases (write/edit/validate…) call the LLM and take 30–90s, so they must
never run inline in a request. We run them on a daemon thread and expose status
for the UI to poll. LLM concurrency is capped separately by ``llm_queue``.
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
        self._shutting_down = False

    def submit(self, kind: str, fn: Callable[[], None], meta: Optional[dict] = None) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            if self._shutting_down:
                raise RuntimeError("Novel OS is restarting — new jobs are not accepted")
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
            from llm_call_context import format_llm_job_label, llm_job_context  # noqa: WPS433

            with self._lock:
                started_at = self._jobs.get(job_id, {}).get("started_at")
            job_label = format_llm_job_label(kind, meta, started_at=started_at)
            ctx_meta = {**(meta or {}), "kind": kind}
            try:
                with llm_job_context(job_label, meta=ctx_meta):
                    fn()
                with self._lock:
                    job = self._jobs.get(job_id)
                    if job and job["status"] == "running":
                        self._update_unlocked(job_id, status="done")
            except Exception as e:  # noqa: BLE001 - surface any agent failure to the UI
                self._update(job_id, status="error", error=f"{type(e).__name__}: {e}")

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def _update_unlocked(self, job_id: str, **fields) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.update(fields)
            job["finished_at"] = _now()

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            self._update_unlocked(job_id, **fields)

    def flush(self, reason: str = "Cancelled by restart") -> int:
        """Mark all in-flight jobs failed and reject new submissions."""
        with self._lock:
            self._shutting_down = True
            count = 0
            for job in self._jobs.values():
                if job["status"] == "running":
                    job["status"] = "error"
                    job["error"] = reason
                    job["finished_at"] = _now()
                    count += 1
            return count

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_running(self) -> list[dict]:
        from llm_call_context import format_llm_job_label, screen_for_kind  # noqa: WPS433

        _meta_keys = frozenset({
            "job_id", "kind", "status", "error", "started_at", "finished_at",
        })
        with self._lock:
            rows: list[dict] = []
            for job in self._jobs.values():
                if job.get("status") != "running":
                    continue
                meta = {k: v for k, v in job.items() if k not in _meta_keys}
                kind = str(job.get("kind", ""))
                rows.append({
                    "job_id": job["job_id"],
                    "kind": kind,
                    "label": format_llm_job_label(
                        kind, meta, started_at=job.get("started_at"),
                    ),
                    "started_at": job.get("started_at") or _now(),
                    "project_id": job.get("project_id"),
                    "chapter": job.get("chapter"),
                    "screen": screen_for_kind(kind, meta),
                })
            rows.sort(key=lambda r: r["started_at"])
            return rows


# Process-wide singleton.
runner = JobRunner()
