"""Background job runner for agent work.

LLM calls block for seconds to minutes, so they run on a thread pool. Each job
is tracked as a Run row and announces progress on the event bus.

    run = jobs.submit(project_id, "draft", fn, agent_id=..., chapter=3, input={...})
    # fn(run_id) -> dict output; raise to fail.
"""

from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from sqlmodel import Session

from . import events
from .db import engine, session_scope
from .models import Run
from .models.base import now

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="novel-os-agent")

# ---- cooperative cancellation ----------------------------------------------------------
# A running job can't be killed from outside, so cancel() raises a flag and the
# job checks it (jobs.check(run_id)) between steps and inside streaming callbacks.

_cancelled: set[str] = set()
_cancel_lock = threading.Lock()


class Cancelled(Exception):
    """Raised inside a job when the author stopped its run."""


def request_cancel(run_id: str) -> None:
    with _cancel_lock:
        _cancelled.add(run_id)


def is_cancelled(run_id: str) -> bool:
    with _cancel_lock:
        return run_id in _cancelled


def check(run_id: str) -> None:
    """Raise Cancelled if this run was stopped."""
    if is_cancelled(run_id):
        raise Cancelled(run_id)


def cancel(run_id: str) -> Optional[str]:
    """Stop a run. Queued runs become cancelled at once; running runs are flagged
    and stop at their next check. Returns the run's status afterwards (None if missing)."""
    with session_scope() as s:
        run = s.get(Run, run_id)
        if not run:
            return None
        project_id, status = run.project_id, run.status
        if status == "queued":
            run.status = "cancelled"
            run.error = "Stopped by the author"
            run.finished_at = now()
            s.add(run)
    if status == "queued":
        request_cancel(run_id)  # in case a worker picks it up concurrently
        events.publish(project_id, "run.updated", {"id": run_id, "status": "cancelled"})
        return "cancelled"
    if status == "running":
        request_cancel(run_id)
        events.publish(project_id, "run.updated", {"id": run_id, "status": "running", "cancelling": True})
    return status


def submit(project_id: str, task: str, fn: Callable[[str], dict], *, agent_id: Optional[str] = None,
           chapter: Optional[int] = None, input: Optional[dict] = None) -> Run:
    with Session(engine()) as s:
        run = Run(project_id=project_id, agent_id=agent_id, task=task, chapter=chapter, input=input or {})
        s.add(run)
        s.commit()
        s.refresh(run)
    events.publish(project_id, "run.updated", {"id": run.id, "status": run.status, "task": task})
    _pool.submit(_execute, run.id, project_id, fn)
    return run


def _set(run_id: str, **fields) -> Run:
    with session_scope() as s:
        run = s.get(Run, run_id)
        for k, v in fields.items():
            setattr(run, k, v)
        s.add(run)
        s.flush()
        s.refresh(run)
        s.expunge(run)
        return run


def _execute(run_id: str, project_id: str, fn: Callable[[str], dict]) -> None:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None or run.status == "cancelled":
            with _cancel_lock:
                _cancelled.discard(run_id)
            return  # stopped while still queued
        run.status = "running"
        s.add(run)
    events.publish(project_id, "run.updated", {"id": run_id, "status": "running"})
    try:
        check(run_id)
        out = fn(run_id) or {}
        _set(run_id, status="done", output=out, finished_at=now())
        events.publish(project_id, "run.updated", {"id": run_id, "status": "done"})
    except Cancelled:
        _set(run_id, status="cancelled", error="Stopped by the author", finished_at=now())
        events.publish(project_id, "run.updated", {"id": run_id, "status": "cancelled"})
    except Exception as e:  # noqa: BLE001 - surface every failure to the UI
        traceback.print_exc()
        _set(run_id, status="failed", error=f"{type(e).__name__}: {e}", finished_at=now())
        events.publish(project_id, "run.updated", {"id": run_id, "status": "failed", "error": str(e)})
    finally:
        with _cancel_lock:
            _cancelled.discard(run_id)


def run_inline(fn: Callable[[str], dict], run_id: str = "inline") -> dict:
    """Tests: execute synchronously."""
    return fn(run_id)
