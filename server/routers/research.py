"""Research swarm: ask a question, browser agents search, read and cite."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from .. import events
from ..db import get_session
from ..models import CodexEntry, Memory, ResearchSource, ResearchTask
from ..models.base import now
from ..research import browser, search as search_mod, swarm
from .projects import get_project

router = APIRouter(tags=["research"])


class ResearchIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    chapter: Optional[int] = None


class FileIn(BaseModel):
    entry_id: Optional[str] = None  # append to this Codex entry
    name: Optional[str] = None  # or find/create an entry by name
    kind: str = "lore"


class SourceOut(BaseModel):
    id: str
    task_id: str
    url: str
    domain: str
    title: str
    excerpt: str
    note: str
    reliability: float
    filed_to_codex_id: Optional[str]
    created_at: str


class TaskOut(BaseModel):
    id: str
    project_id: str
    question: str
    chapter: Optional[int]
    status: str
    progress: str
    summary: str
    source_count: int = 0
    created_at: str
    finished_at: Optional[str]


class TaskDetail(TaskOut):
    sources: list[SourceOut] = []


class TaskList(BaseModel):
    tasks: list[TaskOut]
    browsers: int
    sources: int
    backend: str
    search_provider: str


def _src(s: ResearchSource) -> SourceOut:
    return SourceOut(id=s.id, task_id=s.task_id, url=s.url, domain=swarm.domain(s.url), title=s.title,
                     excerpt=s.excerpt, note=s.note, reliability=s.reliability,
                     filed_to_codex_id=s.filed_to_codex_id, created_at=s.created_at.isoformat())


def _task(t: ResearchTask, count: int = 0) -> TaskOut:
    return TaskOut(id=t.id, project_id=t.project_id, question=t.question, chapter=t.chapter, status=t.status,
                   progress=t.progress, summary=t.summary, source_count=count,
                   created_at=t.created_at.isoformat(),
                   finished_at=t.finished_at.isoformat() if t.finished_at else None)


def _get_task(session: Session, project_id: str, task_id: str) -> ResearchTask:
    t = session.get(ResearchTask, task_id)
    if not t or t.project_id != project_id:
        raise HTTPException(404, "Research task not found")
    return t


def _detail(session: Session, t: ResearchTask) -> TaskDetail:
    sources = swarm.list_sources(session, t.id)
    return TaskDetail(**_task(t, len(sources)).model_dump(), sources=[_src(s) for s in sources])


def _clear(session: Session, t: ResearchTask) -> None:
    for s in session.exec(select(ResearchSource).where(ResearchSource.task_id == t.id)).all():
        session.delete(s)
    for m in session.exec(select(Memory).where(Memory.source == f"research:{t.id}")).all():
        session.delete(m)


@router.get("/projects/{project_id}/research", response_model=TaskList)
def list_tasks(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    counts = dict(session.exec(
        select(ResearchSource.task_id, func.count(ResearchSource.id))
        .join(ResearchTask, ResearchTask.id == ResearchSource.task_id)
        .where(ResearchTask.project_id == project_id)
        .group_by(ResearchSource.task_id)
    ).all())
    tasks = session.exec(select(ResearchTask).where(ResearchTask.project_id == project_id)
                         .order_by(ResearchTask.created_at.desc())).all()
    return TaskList(tasks=[_task(t, counts.get(t.id, 0)) for t in tasks],
                    browsers=swarm.active_workers() or swarm.MAX_WORKERS,
                    sources=sum(counts.values()), backend=browser.backend_name(),
                    search_provider=search_mod.provider_name())


@router.post("/projects/{project_id}/research", response_model=TaskDetail, status_code=201)
def create_task(project_id: str, body: ResearchIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    task = swarm.create(session, project_id, body.question, body.chapter)
    swarm.submit(project_id, task.id, body.chapter)
    session.refresh(task)
    return _detail(session, task)


@router.get("/projects/{project_id}/research/suggestions", response_model=list[str])
def suggestions(project_id: str, session: Session = Depends(get_session)):
    """Prompts drawn from the book: period details, places, professions."""
    p = get_project(session, project_id)
    bible = p.bible or {}
    era = str(bible.get("era") or bible.get("period") or "").strip()
    setting = bible.get("setting")
    setting = setting if isinstance(setting, str) else ""
    when = f" in {era}" if era else ""
    out: list[str] = []
    places = session.exec(select(CodexEntry.name).where(CodexEntry.project_id == project_id,
                                                         CodexEntry.kind == "location").limit(2)).all()
    for place in places:
        out.append(f"What would {place} have looked, sounded and smelled like{when}?")
    people = session.exec(select(CodexEntry).where(CodexEntry.project_id == project_id,
                                                    CodexEntry.kind == "character").limit(6)).all()
    for c in people:
        job = (c.facts or {}).get("occupation") or (c.facts or {}).get("profession")
        if job:
            out.append(f"What did a typical working day look like for a {job}{when}?")
            break
    if era:
        out.append(f"Everyday prices, food and clothing{when}")
        out.append(f"How did people travel and send news{when}?")
    if setting:
        out.append(f"Climate, landscape and seasons of {setting}")
    if p.genre:
        out.append(f"Details readers of {p.genre.lower()} expect to be accurate")
    if len(out) < 3:
        out += ["Period-accurate slang and forms of address",
                "Medical knowledge and common remedies of the period",
                "Professions my characters could plausibly hold"]
    seen: set[str] = set()
    return [x for x in out if not (x in seen or seen.add(x))][:6]


@router.get("/projects/{project_id}/research/{task_id}", response_model=TaskDetail)
def get_task(project_id: str, task_id: str, session: Session = Depends(get_session)):
    return _detail(session, _get_task(session, project_id, task_id))


@router.post("/projects/{project_id}/research/{task_id}/cancel", response_model=TaskDetail)
def cancel_task(project_id: str, task_id: str, session: Session = Depends(get_session)):
    t = _get_task(session, project_id, task_id)
    if t.status not in ("done", "failed", "cancelled"):
        t.status, t.progress, t.finished_at = "cancelled", "Cancelled", now()
        session.add(t)
        session.commit()
        session.refresh(t)
        events.publish(project_id, "research.updated", {"id": t.id, "status": "cancelled"})
    return _detail(session, t)


@router.post("/projects/{project_id}/research/{task_id}/retry", response_model=TaskDetail)
def retry_task(project_id: str, task_id: str, session: Session = Depends(get_session)):
    t = _get_task(session, project_id, task_id)
    if t.status in ("queued", "browsing", "synthesizing"):
        raise HTTPException(409, "Task is still running")
    _clear(session, t)
    t.status, t.progress, t.summary, t.finished_at = "queued", "Queued", "", None
    session.add(t)
    session.commit()
    swarm.submit(project_id, t.id, t.chapter)
    session.refresh(t)
    return _detail(session, t)


@router.delete("/projects/{project_id}/research/{task_id}", status_code=204)
def delete_task(project_id: str, task_id: str, session: Session = Depends(get_session)):
    t = _get_task(session, project_id, task_id)
    t.status = "cancelled"  # stops a running swarm at its next checkpoint
    session.add(t)
    session.flush()
    _clear(session, t)
    session.delete(t)
    session.commit()
    events.publish(project_id, "research.updated", {"id": task_id, "deleted": True})


@router.post("/projects/{project_id}/research/sources/{source_id}/file", response_model=SourceOut)
def file_source(project_id: str, source_id: str, body: FileIn, session: Session = Depends(get_session)):
    """File a finding into the Codex: append to an entry's notes with a citation."""
    src = session.get(ResearchSource, source_id)
    task = session.get(ResearchTask, src.task_id) if src else None
    if not src or not task or task.project_id != project_id:
        raise HTTPException(404, "Source not found")
    entry: Optional[CodexEntry] = None
    if body.entry_id:
        entry = session.get(CodexEntry, body.entry_id)
        if not entry or entry.project_id != project_id:
            raise HTTPException(404, "Codex entry not found")
    else:
        name = (body.name or "").strip() or f"Research: {task.question[:80]}"
        entry = session.exec(select(CodexEntry).where(CodexEntry.project_id == project_id,
                                                      func.lower(CodexEntry.name) == name.lower())).first()
        if not entry:
            entry = CodexEntry(project_id=project_id, kind=body.kind or "lore", name=name,
                               summary=src.note[:300])
    citation = f"{src.note}"
    if src.excerpt:
        citation += f'\n> "{src.excerpt}"'
    citation += f"\nSource: {src.title or swarm.domain(src.url)}, {src.url}"
    entry.notes = (entry.notes.rstrip() + "\n\n" if entry.notes.strip() else "") + citation
    entry.updated_at = now()
    session.add(entry)
    session.flush()
    src.filed_to_codex_id = entry.id
    session.add(src)
    session.commit()
    session.refresh(src)
    events.publish(project_id, "codex.updated", {"id": entry.id})
    events.publish(project_id, "research.updated", {"id": task.id, "source": src.id})
    return _src(src)
