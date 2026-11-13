"""Codex proposals: entries suggested from the chapters. List, find more, accept, dismiss."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events
from ..agents import extract as ex
from ..agents import memory as mem
from ..db import get_session
from ..models import CodexEntry
from ..models.codex_extra import CodexProposal
from .projects import get_project

# Mounted by `_codex_proposals_first.py`, which sorts before book.py so GET /codex/proposals
# isn't swallowed by book's GET /codex/{entry_id}. (No `router` name here, or it'd mount twice.)
proposals_router = APIRouter(tags=["codex"])
P = "/projects/{project_id}/codex/proposals"


class ProposeIn(BaseModel):
    chapter: Optional[int] = None


class ProposalOut(BaseModel):
    id: str
    name: str
    kind: str
    summary: str
    first_chapter: Optional[int]
    evidence: str
    status: str
    created_at: str


def _out(x: CodexProposal) -> ProposalOut:
    return ProposalOut(id=x.id, name=x.name, kind=x.kind, summary=x.summary, first_chapter=x.first_chapter,
                       evidence=x.evidence, status=x.status, created_at=x.created_at.isoformat())


def _get(session: Session, project_id: str, pid: str) -> CodexProposal:
    get_project(session, project_id)
    x = session.get(CodexProposal, pid)
    if not x or x.project_id != project_id:
        raise HTTPException(404, "Proposal not found")
    if x.status != "open":
        raise HTTPException(409, f"Proposal already {x.status}")
    return x


@proposals_router.get(P, response_model=list[ProposalOut])
def list_proposals(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    rows = session.exec(select(CodexProposal).where(CodexProposal.project_id == project_id,
                                                    CodexProposal.status == "open")
                        .order_by(CodexProposal.first_chapter, CodexProposal.name)).all()
    return [_out(x) for x in rows]


@proposals_router.post(P, status_code=202)
def find_proposals(project_id: str, body: ProposeIn | None = None, session: Session = Depends(get_session)):
    get_project(session, project_id)
    try:
        run = ex.propose(project_id, body.chapter if body else None)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"run_id": run.id}


@proposals_router.post(P + "/{pid}/accept")
def accept(project_id: str, pid: str, session: Session = Depends(get_session)):
    x = _get(session, project_id, pid)
    e = CodexEntry(project_id=project_id, kind=x.kind, name=x.name, summary=x.summary,
                   first_chapter=x.first_chapter, last_chapter=x.first_chapter)
    x.status = "accepted"
    session.add(e)
    session.add(x)
    session.commit()
    session.refresh(e)
    fact = f"{x.name} ({x.kind})" + (f": {x.summary}" if x.summary else "")
    mem.remember(session, project_id, kind="fact", content=fact, chapter=x.first_chapter,
                 source=f"codex:{e.id}", importance=0.6)
    events.publish(project_id, "codex.updated", {"id": e.id, "accepted": pid})
    events.publish(project_id, "memory.updated", {"source": f"codex:{e.id}"})
    return {"proposal": _out(x), "entry": e.model_dump(mode="json")}


@proposals_router.post(P + "/{pid}/dismiss", response_model=ProposalOut)
def dismiss(project_id: str, pid: str, session: Session = Depends(get_session)):
    x = _get(session, project_id, pid)
    x.status = "dismissed"  # the row stays, so the name is never proposed again
    session.add(x)
    session.commit()
    session.refresh(x)
    events.publish(project_id, "codex.updated", {"dismissed": pid})
    return _out(x)
