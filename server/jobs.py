"""Background job runner for agent work.

LLM calls block for seconds to minutes, so they run on a thread pool. Each job
is tracked as a Run row and announces progress on the event bus.

    run = jobs.submit(project_id, "draft", fn, agent_id=..., chapter=3, input={...})
    # fn(run_id) -> dict output; raise to fail.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from sqlmodel import Session

from . import events
from .db import engine, session_scope
from .models import Run
from .models.base import now

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="novel-os-agent")


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
    _set(run_id, status="running")
    events.publish(project_id, "run.updated", {"id": run_id, "status": "running"})
    try:
        out = fn(run_id) or {}
        _set(run_id, status="done", output=out, finished_at=now())
        events.publish(project_id, "run.updated", {"id": run_id, "status": "done"})
    except Exception as e:  # noqa: BLE001 - surface every failure to the UI
        traceback.print_exc()
        _set(run_id, status="failed", error=f"{type(e).__name__}: {e}", finished_at=now())
        events.publish(project_id, "run.updated", {"id": run_id, "status": "failed", "error": str(e)})


def run_inline(fn: Callable[[str], dict], run_id: str = "inline") -> dict:
    """Tests: execute synchronously."""
    return fn(run_id)
