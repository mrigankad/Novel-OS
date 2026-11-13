"""What agents remember: list, search, add, pin, edit, forget."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events
from ..agents import memory as mem
from ..db import get_session
from ..models import Memory, Project

router = APIRouter(tags=["memory"])


class MemoryIn(BaseModel):
    kind: str = "fact"
    content: str
    agent_id: Optional[str] = None
    chapter: Optional[int] = None
    importance: float = 0.5
    pinned: bool = False
    source: str = "author"


class MemoryPatch(BaseModel):
    content: Optional[str] = None
    kind: Optional[str] = None
    importance: Optional[float] = None
    pinned: Optional[bool] = None
    chapter: Optional[int] = None
    agent_id: Optional[str] = None


class MemoryOut(BaseModel):
    id: str
    kind: str
    content: str
    agent_id: Optional[str]
    chapter: Optional[int]
    source: str
    importance: float
    pinned: bool
    recall_count: int
    last_recalled_at: Optional[str]
    created_at: str


def out(m: Memory) -> MemoryOut:
    return MemoryOut(id=m.id, kind=m.kind, content=m.content, agent_id=m.agent_id, chapter=m.chapter, source=m.source,
                     importance=m.importance, pinned=m.pinned, recall_count=m.recall_count,
                     last_recalled_at=m.last_recalled_at.isoformat() if m.last_recalled_at else None,
                     created_at=m.created_at.isoformat())


def _get(s: Session, pid: str, mid: str) -> Memory:
    m = s.get(Memory, mid)
    if not m or m.project_id != pid:
        raise HTTPException(404, "Memory not found")
    return m


@router.get("/projects/{pid}/memory", response_model=list[MemoryOut])
def list_memory(pid: str, kind: Optional[str] = None, agent_id: Optional[str] = None, chapter: Optional[int] = None,
                q: str = "", limit: int = 300, s: Session = Depends(get_session)):
    if not s.get(Project, pid):
        raise HTTPException(404, "Project not found")
    stmt = select(Memory).where(Memory.project_id == pid)
    if kind:
        stmt = stmt.where(Memory.kind == kind)
    if agent_id == "shared":
        stmt = stmt.where(Memory.agent_id == None)  # noqa: E711
    elif agent_id:
        stmt = stmt.where(Memory.agent_id == agent_id)
    if chapter is not None:
        stmt = stmt.where(Memory.chapter == chapter)
    rows = list(s.exec(stmt.order_by(Memory.pinned.desc(), Memory.created_at.desc()).limit(mem.MAX_CANDIDATES)).all())
    if q.strip():
        qt = set(mem.tokens(q))
        low = q.lower().strip()
        rows = [m for _, m in mem.score_memories(rows, q, chapter)
                if low in m.content.lower() or qt & set(mem.tokens(m.content))]
    return [out(m) for m in rows[:min(limit, 500)]]


@router.post("/projects/{pid}/memory", response_model=MemoryOut, status_code=201)
def create_memory(pid: str, body: MemoryIn, s: Session = Depends(get_session)):
    if not s.get(Project, pid):
        raise HTTPException(404, "Project not found")
    if not body.content.strip():
        raise HTTPException(422, "content is required")
    return out(mem.remember(s, pid, body.kind, body.content, agent_id=body.agent_id, chapter=body.chapter,
                            source=body.source, importance=body.importance, pinned=body.pinned))


@router.post("/projects/{pid}/memory/recall", response_model=list[MemoryOut])
def recall(pid: str, body: dict, s: Session = Depends(get_session)):
    """Preview what an agent would recall for a query (debug / 'in context' view)."""
    return [out(m) for m in mem.recall(s, pid, str(body.get("query", "")), agent_id=body.get("agent_id"),
                                       chapter=body.get("chapter"), k=int(body.get("k", 12)), touch=False)]


@router.patch("/projects/{pid}/memory/{mid}", response_model=MemoryOut)
def update_memory(pid: str, mid: str, body: MemoryPatch, s: Session = Depends(get_session)):
    m = _get(s, pid, mid)
    data = body.model_dump(exclude_unset=True)
    if "importance" in data and data["importance"] is not None:
        data["importance"] = max(0.0, min(1.0, data["importance"]))
    for k, v in data.items():
        setattr(m, k, v)
    s.add(m)
    s.commit()
    s.refresh(m)
    events.publish(pid, "memory.updated", {"id": m.id})
    return out(m)


@router.delete("/projects/{pid}/memory/{mid}", status_code=204)
def delete_memory(pid: str, mid: str, s: Session = Depends(get_session)):
    s.delete(_get(s, pid, mid))
    s.commit()
    events.publish(pid, "memory.updated", {"id": mid})
