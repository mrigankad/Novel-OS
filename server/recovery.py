"""Startup recovery: work that was in flight when the server stopped can't resume
(jobs run on an in-process thread pool), so mark it failed with a clear reason.
The UI then offers Retry instead of a spinner that never ends."""

from __future__ import annotations

from sqlmodel import Session, select

from .db import engine
from .models import ResearchTask, Run
from .models.base import now

INTERRUPTED = "Interrupted: the Novel OS server restarted while this was running. Retry it."


def recover_interrupted() -> dict:
    with Session(engine()) as s:
        runs = s.exec(select(Run).where(Run.status.in_(("queued", "running")))).all()
        for r in runs:
            r.status, r.error, r.finished_at = "failed", INTERRUPTED, now()
            s.add(r)
        tasks = s.exec(select(ResearchTask).where(
            ResearchTask.status.in_(("queued", "browsing", "synthesizing")))).all()
        for t in tasks:
            t.status, t.progress, t.finished_at = "failed", INTERRUPTED, now()
            s.add(t)
        s.commit()
        return {"runs": len(runs), "research": len(tasks)}
