"""The manuscript: chapters, versions, Codex, plot threads, continuity, the sample book."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, func, or_, select

from .. import events
from ..db import get_session
from ..models import (
    Agent, Chapter, ChapterVersion, CodexEntry, CodexLink, ContinuityExemption, Memory, PlotThread, Project,
)
from ..models.base import now
from ..services import book as svc
from ..services.continuity import continuity_findings
from .projects import ProjectOut, _out as project_out, get_project

router = APIRouter(tags=["book"])
P = "/projects/{project_id}"


def _touch(session: Session, project_id: str) -> None:
    p = session.get(Project, project_id)
    if p:
        p.updated_at = now()
        session.add(p)


# ===================================================================== chapters

class ChapterRow(BaseModel):
    id: str
    number: int
    title: str
    act: int
    pov: str
    status: str
    synopsis: str
    beats: list
    word_count: int
    target_words: int
    assigned_agent_id: Optional[str]
    assigned_agent_name: Optional[str] = None
    updated_at: str


class ChapterOut(ChapterRow):
    text: str
    doc: dict


class ChapterIn(BaseModel):
    title: str = ""
    act: Optional[int] = None
    pov: str = ""
    status: str = "planned"
    synopsis: str = ""
    beats: list = []
    target_words: int = 3000
    text: str = ""


class ChapterPatch(BaseModel):
    title: Optional[str] = None
    act: Optional[int] = None
    pov: Optional[str] = None
    status: Optional[str] = None
    synopsis: Optional[str] = None
    beats: Optional[list] = None
    target_words: Optional[int] = None
    text: Optional[str] = None
    doc: Optional[dict] = None
    assigned_agent_id: Optional[str] = None


class ReorderIn(BaseModel):
    order: list[str]  # chapter ids in their new order


def _row(c: Chapter, agent_names: dict[str, str], full: bool = False):
    base = dict(id=c.id, number=c.number, title=c.title, act=c.act, pov=c.pov, status=c.status,
                synopsis=c.synopsis, beats=c.beats or [], word_count=c.word_count, target_words=c.target_words,
                assigned_agent_id=c.assigned_agent_id,
                assigned_agent_name=agent_names.get(c.assigned_agent_id or ""),
                updated_at=c.updated_at.isoformat())
    return ChapterOut(**base, text=c.text, doc=c.doc or {}) if full else ChapterRow(**base)


def _agent_names(session: Session, project_id: str) -> dict[str, str]:
    return {a.id: a.name for a in session.exec(select(Agent).where(Agent.project_id == project_id)).all()}


def _chapter(session: Session, project_id: str, n: int) -> Chapter:
    c = session.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == n)).first()
    if not c:
        raise HTTPException(404, "Chapter not found")
    return c


def _chapters(session: Session, project_id: str) -> list[Chapter]:
    return list(session.exec(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.number)).all())


def _renumber(session: Session, ordered: list[Chapter]) -> None:
    """Two passes so the (project_id, number) unique constraint never collides."""
    for i, c in enumerate(ordered):
        c.number = -(i + 1)
        session.add(c)
    session.flush()
    for i, c in enumerate(ordered):
        c.number = i + 1
        session.add(c)
    session.flush()


@router.get(P + "/chapters", response_model=list[ChapterRow])
def list_chapters(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    names = _agent_names(session, project_id)
    return [_row(c, names) for c in _chapters(session, project_id)]


@router.post(P + "/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(project_id: str, body: ChapterIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    last = session.exec(select(Chapter).where(Chapter.project_id == project_id)
                        .order_by(Chapter.number.desc())).first()
    data = body.model_dump()
    data["act"] = data["act"] or (last.act if last else 1)
    c = Chapter(project_id=project_id, number=(last.number + 1) if last else 1,
                word_count=svc.word_count(body.text), **data)
    session.add(c)
    _touch(session, project_id)
    session.commit()
    session.refresh(c)
    events.publish(project_id, "chapter.updated", {"number": c.number, "id": c.id})
    return _row(c, _agent_names(session, project_id), full=True)


@router.get(P + "/chapters/{n}", response_model=ChapterOut)
def read_chapter(project_id: str, n: int, session: Session = Depends(get_session)):
    return _row(_chapter(session, project_id, n), _agent_names(session, project_id), full=True)


@router.patch(P + "/chapters/{n}", response_model=ChapterOut)
def update_chapter(project_id: str, n: int, body: ChapterPatch, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    data = body.model_dump(exclude_unset=True)
    previous = c.text
    for k, v in data.items():
        if k == "assigned_agent_id" and v == "":
            v = None
        setattr(c, k, v)
    if "text" in data:
        c.word_count = svc.word_count(c.text)
        if c.status == "planned" and c.word_count > 0:
            c.status = "drafting"
    c.updated_at = now()
    session.add(c)
    if "text" in data and c.text != previous:
        svc.maybe_auto_snapshot(session, c, previous)
    _touch(session, project_id)
    session.commit()
    session.refresh(c)
    events.publish(project_id, "chapter.updated", {"number": c.number, "id": c.id})
    return _row(c, _agent_names(session, project_id), full=True)


@router.delete(P + "/chapters/{n}", status_code=204)
def delete_chapter(project_id: str, n: int, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    session.exec(sa_delete(ChapterVersion).where(ChapterVersion.chapter_id == c.id))
    session.delete(c)
    session.flush()
    _renumber(session, _chapters(session, project_id))
    _touch(session, project_id)
    session.commit()
    events.publish(project_id, "chapter.updated", {"deleted": n})


@router.post(P + "/chapters/reorder", response_model=list[ChapterRow])
def reorder_chapters(project_id: str, body: ReorderIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    current = {c.id: c for c in _chapters(session, project_id)}
    if set(body.order) != set(current) or len(body.order) != len(current):
        raise HTTPException(422, "order must list every chapter id exactly once")
    _renumber(session, [current[i] for i in body.order])
    _touch(session, project_id)
    session.commit()
    events.publish(project_id, "chapter.updated", {"reordered": True})
    return list_chapters(project_id, session)


# ===================================================================== versions

class VersionOut(BaseModel):
    id: str
    chapter_id: str
    kind: str
    text: str
    word_count: int
    produced_by: str
    model: str
    note: str
    created_at: str


class SnapshotIn(BaseModel):
    note: str = ""
    kind: str = "snapshot"


def _vout(v: ChapterVersion) -> VersionOut:
    return VersionOut(**v.model_dump(exclude={"created_at"}), created_at=v.created_at.isoformat())


@router.get(P + "/chapters/{n}/versions", response_model=list[VersionOut])
def list_versions(project_id: str, n: int, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    rows = session.exec(select(ChapterVersion).where(ChapterVersion.chapter_id == c.id)
                        .order_by(ChapterVersion.created_at.desc())).all()
    return [_vout(v) for v in rows]


@router.post(P + "/chapters/{n}/versions", response_model=VersionOut, status_code=201)
def create_version(project_id: str, n: int, body: SnapshotIn, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    v = svc.snapshot(session, c, kind=body.kind or "snapshot", note=body.note)
    session.commit()
    session.refresh(v)
    events.publish(project_id, "chapter.updated", {"number": c.number, "version": v.id})
    return _vout(v)


@router.post(P + "/versions/{version_id}/restore", response_model=ChapterOut)
def restore_version(project_id: str, version_id: str, session: Session = Depends(get_session)):
    v = session.get(ChapterVersion, version_id)
    c = session.get(Chapter, v.chapter_id) if v else None
    if not v or not c or c.project_id != project_id:
        raise HTTPException(404, "Version not found")
    if c.text != v.text:
        svc.snapshot(session, c, kind="snapshot", note="Before restore")
    c.text = v.text
    c.word_count = svc.word_count(v.text)
    c.doc = {}  # the editor rebuilds its document from the restored text
    c.updated_at = now()
    session.add(c)
    _touch(session, project_id)
    session.commit()
    session.refresh(c)
    events.publish(project_id, "chapter.updated", {"number": c.number, "id": c.id, "restored": version_id})
    return _row(c, _agent_names(session, project_id), full=True)


# ===================================================================== codex

class CodexIn(BaseModel):
    kind: str
    name: str
    aliases: list = []
    role: str = ""
    summary: str = ""
    facts: dict = {}
    notes: str = ""
    first_chapter: Optional[int] = None
    last_chapter: Optional[int] = None


class CodexPatch(BaseModel):
    kind: Optional[str] = None
    name: Optional[str] = None
    aliases: Optional[list] = None
    role: Optional[str] = None
    summary: Optional[str] = None
    facts: Optional[dict] = None
    notes: Optional[str] = None
    image_media_id: Optional[str] = None
    first_chapter: Optional[int] = None
    last_chapter: Optional[int] = None


class CodexOut(CodexIn):
    id: str
    image_media_id: Optional[str]
    updated_at: str


def _cout(e: CodexEntry) -> CodexOut:
    return CodexOut(**e.model_dump(exclude={"created_at", "updated_at", "project_id"}),
                    updated_at=e.updated_at.isoformat())


def _entry(session: Session, project_id: str, entry_id: str) -> CodexEntry:
    e = session.get(CodexEntry, entry_id)
    if not e or e.project_id != project_id:
        raise HTTPException(404, "Codex entry not found")
    return e


@router.get(P + "/codex", response_model=list[CodexOut])
def list_codex(project_id: str, kind: Optional[str] = None, q: Optional[str] = None,
               session: Session = Depends(get_session)):
    get_project(session, project_id)
    stmt = select(CodexEntry).where(CodexEntry.project_id == project_id)
    if kind:
        stmt = stmt.where(CodexEntry.kind == kind)
    rows = session.exec(stmt.order_by(CodexEntry.kind, CodexEntry.name)).all()
    if q:
        needle = q.strip().lower()
        rows = [e for e in rows if needle in e.name.lower()
                or any(needle in str(a).lower() for a in (e.aliases or []))]
    return [_cout(e) for e in rows]


@router.post(P + "/codex", response_model=CodexOut, status_code=201)
def create_codex(project_id: str, body: CodexIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    e = CodexEntry(project_id=project_id, **body.model_dump())
    session.add(e)
    _touch(session, project_id)
    session.commit()
    session.refresh(e)
    events.publish(project_id, "codex.updated", {"id": e.id})
    return _cout(e)


@router.get(P + "/codex/{entry_id}", response_model=CodexOut)
def read_codex(project_id: str, entry_id: str, session: Session = Depends(get_session)):
    return _cout(_entry(session, project_id, entry_id))


@router.patch(P + "/codex/{entry_id}", response_model=CodexOut)
def update_codex(project_id: str, entry_id: str, body: CodexPatch, session: Session = Depends(get_session)):
    e = _entry(session, project_id, entry_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    e.updated_at = now()
    session.add(e)
    session.commit()
    session.refresh(e)
    events.publish(project_id, "codex.updated", {"id": e.id})
    return _cout(e)


@router.delete(P + "/codex/{entry_id}", status_code=204)
def delete_codex(project_id: str, entry_id: str, session: Session = Depends(get_session)):
    e = _entry(session, project_id, entry_id)
    session.exec(sa_delete(CodexLink).where(
        or_(CodexLink.source_id == entry_id, CodexLink.target_id == entry_id)))
    session.delete(e)
    session.commit()
    events.publish(project_id, "codex.updated", {"id": entry_id, "deleted": True})


# ---- links

class LinkIn(BaseModel):
    source_id: str
    target_id: str
    label: str = ""
    since_chapter: Optional[int] = None


class LinkOut(LinkIn):
    id: str


@router.get(P + "/codex-links", response_model=list[LinkOut])
def list_links(project_id: str, entry: Optional[str] = None, session: Session = Depends(get_session)):
    stmt = select(CodexLink).where(CodexLink.project_id == project_id)
    if entry:
        stmt = stmt.where(or_(CodexLink.source_id == entry, CodexLink.target_id == entry))
    return [LinkOut(**link.model_dump(exclude={"project_id"})) for link in session.exec(stmt).all()]


@router.post(P + "/codex-links", response_model=LinkOut, status_code=201)
def create_link(project_id: str, body: LinkIn, session: Session = Depends(get_session)):
    _entry(session, project_id, body.source_id)
    _entry(session, project_id, body.target_id)
    link = CodexLink(project_id=project_id, **body.model_dump())
    session.add(link)
    session.commit()
    session.refresh(link)
    events.publish(project_id, "codex.updated", {"link": link.id})
    return LinkOut(**link.model_dump(exclude={"project_id"}))


@router.delete(P + "/codex-links/{link_id}", status_code=204)
def delete_link(project_id: str, link_id: str, session: Session = Depends(get_session)):
    link = session.get(CodexLink, link_id)
    if not link or link.project_id != project_id:
        raise HTTPException(404, "Link not found")
    session.delete(link)
    session.commit()
    events.publish(project_id, "codex.updated", {"link": link_id, "deleted": True})


# ---- plot threads

class ThreadIn(BaseModel):
    name: str
    kind: str = "subplot"
    status: str = "open"
    priority: int = 2
    planted_chapter: Optional[int] = None
    target_chapter: Optional[int] = None
    last_advanced_chapter: Optional[int] = None
    notes: str = ""


class ThreadPatch(BaseModel):
    name: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    planted_chapter: Optional[int] = None
    target_chapter: Optional[int] = None
    last_advanced_chapter: Optional[int] = None
    notes: Optional[str] = None


class ThreadOut(ThreadIn):
    id: str


def _thread(session: Session, project_id: str, thread_id: str) -> PlotThread:
    t = session.get(PlotThread, thread_id)
    if not t or t.project_id != project_id:
        raise HTTPException(404, "Plot thread not found")
    return t


@router.get(P + "/plot-threads", response_model=list[ThreadOut])
def list_threads(project_id: str, session: Session = Depends(get_session)):
    rows = session.exec(select(PlotThread).where(PlotThread.project_id == project_id)
                        .order_by(PlotThread.priority, PlotThread.name)).all()
    return [ThreadOut(**t.model_dump(exclude={"project_id"})) for t in rows]


@router.post(P + "/plot-threads", response_model=ThreadOut, status_code=201)
def create_thread(project_id: str, body: ThreadIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    t = PlotThread(project_id=project_id, **body.model_dump())
    session.add(t)
    session.commit()
    session.refresh(t)
    events.publish(project_id, "codex.updated", {"thread": t.id})
    return ThreadOut(**t.model_dump(exclude={"project_id"}))


@router.patch(P + "/plot-threads/{thread_id}", response_model=ThreadOut)
def update_thread(project_id: str, thread_id: str, body: ThreadPatch, session: Session = Depends(get_session)):
    t = _thread(session, project_id, thread_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    session.add(t)
    session.commit()
    session.refresh(t)
    events.publish(project_id, "codex.updated", {"thread": t.id})
    return ThreadOut(**t.model_dump(exclude={"project_id"}))


@router.delete(P + "/plot-threads/{thread_id}", status_code=204)
def delete_thread(project_id: str, thread_id: str, session: Session = Depends(get_session)):
    session.delete(_thread(session, project_id, thread_id))
    session.commit()
    events.publish(project_id, "codex.updated", {"thread": thread_id, "deleted": True})


# ===================================================================== continuity

class ExemptionIn(BaseModel):
    key: str
    reason: str = ""
    message: str = ""  # the finding's text, so the decision memory reads well


class ExemptionOut(BaseModel):
    id: str
    finding_key: str
    reason: str
    created_at: str


@router.get(P + "/continuity")
def get_continuity(project_id: str, chapter: Optional[int] = Query(None), session: Session = Depends(get_session)):
    get_project(session, project_id)
    findings = continuity_findings(session, project_id, chapter)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("critical", "warning", "info")}
    return {"findings": findings, "counts": counts}


@router.get(P + "/continuity/exemptions", response_model=list[ExemptionOut])
def list_exemptions(project_id: str, session: Session = Depends(get_session)):
    rows = session.exec(select(ContinuityExemption).where(ContinuityExemption.project_id == project_id)
                        .order_by(ContinuityExemption.created_at.desc())).all()
    return [ExemptionOut(id=x.id, finding_key=x.finding_key, reason=x.reason, created_at=x.created_at.isoformat())
            for x in rows]


@router.post(P + "/continuity/exemptions", response_model=ExemptionOut, status_code=201)
def create_exemption(project_id: str, body: ExemptionIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    existing = session.exec(select(ContinuityExemption).where(
        ContinuityExemption.project_id == project_id, ContinuityExemption.finding_key == body.key)).first()
    if existing:
        x = existing
    else:
        x = ContinuityExemption(project_id=project_id, finding_key=body.key, reason=body.reason)
        session.add(x)
        what = body.message or body.key
        content = f"The author ruled this intentional, not a continuity error: {what}"
        if body.reason:
            content += f" Reason: {body.reason}"
        session.add(Memory(project_id=project_id, agent_id=None, kind="decision", content=content,
                           source="author", importance=0.8))
        session.commit()
        session.refresh(x)
        events.publish(project_id, "memory.created", {"kind": "decision"})
        events.publish(project_id, "codex.updated", {"exemption": body.key})
    return ExemptionOut(id=x.id, finding_key=x.finding_key, reason=x.reason, created_at=x.created_at.isoformat())


@router.delete(P + "/continuity/exemptions/{key:path}", status_code=204)
def delete_exemption(project_id: str, key: str, session: Session = Depends(get_session)):
    rows = session.exec(select(ContinuityExemption).where(
        ContinuityExemption.project_id == project_id, ContinuityExemption.finding_key == key)).all()
    if not rows:
        raise HTTPException(404, "Exemption not found")
    for x in rows:
        session.delete(x)
    session.commit()
    events.publish(project_id, "codex.updated", {"exemption": key, "deleted": True})


# ===================================================================== sample book

@router.post("/projects/sample", response_model=ProjectOut, status_code=201)
def create_sample(session: Session = Depends(get_session)):
    p = svc.create_sample_book(session)
    session.commit()
    session.refresh(p)
    return project_out(session, p)


# Light search used by the command palette: chapters and Codex entries across books.
@router.get("/search")
def search(q: str = "", session: Session = Depends(get_session)):
    needle = f"%{q.strip()}%"
    chapters = session.exec(select(Chapter.project_id, Chapter.number, Chapter.title)
                            .where(func.lower(Chapter.title).like(needle.lower())).limit(20)).all() if q else []
    entries = session.exec(select(CodexEntry.project_id, CodexEntry.id, CodexEntry.name, CodexEntry.kind)
                           .where(func.lower(CodexEntry.name).like(needle.lower())).limit(20)).all() if q else []
    return {
        "chapters": [{"project_id": a, "number": b, "title": c} for a, b, c in chapters],
        "codex": [{"project_id": a, "id": b, "name": c, "kind": d} for a, b, c, d in entries],
    }
