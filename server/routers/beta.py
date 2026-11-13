"""Beta-reader portal.

Author side: /api/projects/{id}/beta/...   (rounds, readers, comments, insights, to-memory, summarize)
Public side: /api/read/{token}             (one reader's view of one round; no other studio data)
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import events
from ..agents import memory as mem
from ..beta import insights as ins
from ..beta import ratelimit
from ..beta import summarize as summ
from ..db import get_session
from ..models import Chapter, Project
from ..models.base import now
from ..models.beta_extra import BetaComment, BetaProgress, BetaReader, BetaRound

router = APIRouter(tags=["beta"])
P = "/projects/{project_id}/beta"
REACTIONS = ("none", "love", "confused", "bored", "hooked")


# ---- shapes ------------------------------------------------------------------------

class RoundIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    chapters: list[int] = Field(min_length=1)
    closes_at: Optional[datetime] = None


class ReaderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = None


class ReaderOut(BaseModel):
    id: str
    round_id: str
    name: str
    email: Optional[str]
    token: str
    link: str
    invited_at: str
    last_seen_at: Optional[str]
    furthest_chapter: int
    finished: bool
    comments: int = 0


class RoundOut(BaseModel):
    id: str
    name: str
    chapters: list[int]
    status: str
    created_at: str
    closes_at: Optional[str]
    readers: list[ReaderOut] = []


class CommentOut(BaseModel):
    id: str
    round_id: str
    reader_id: str
    reader_name: str = ""
    chapter: int
    quote: str
    from_offset: Optional[int]
    to_offset: Optional[int]
    body: str
    reaction: str
    created_at: str
    resolved: bool


class ToMemoryIn(BaseModel):
    binding: bool = False


class CommentIn(BaseModel):
    chapter: int
    quote: str = Field(default="", max_length=2000)
    from_offset: Optional[int] = None
    to_offset: Optional[int] = None
    body: str = Field(default="", max_length=4000)
    reaction: str = "none"


class ProgressIn(BaseModel):
    chapter: int
    percent: int = Field(ge=0, le=100)
    seconds: int = Field(default=0, ge=0, le=3600)


def _iso(d: Optional[datetime]) -> Optional[str]:
    return d.isoformat() if d else None


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _reader_out(r: BetaReader, comments: int = 0) -> ReaderOut:
    return ReaderOut(id=r.id, round_id=r.round_id, name=r.name, email=r.email, token=r.token,
                     link=f"/read/{r.token}", invited_at=r.invited_at.isoformat(),
                     last_seen_at=_iso(r.last_seen_at), furthest_chapter=r.furthest_chapter,
                     finished=r.finished, comments=comments)


def _comment_out(c: BetaComment, name: str = "") -> CommentOut:
    return CommentOut(id=c.id, round_id=c.round_id, reader_id=c.reader_id, reader_name=name, chapter=c.chapter,
                      quote=c.quote, from_offset=c.from_offset, to_offset=c.to_offset, body=c.body,
                      reaction=c.reaction, created_at=c.created_at.isoformat(), resolved=c.resolved)


def _project(session: Session, project_id: str) -> Project:
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _round(session: Session, project_id: str, rid: str) -> BetaRound:
    r = session.get(BetaRound, rid)
    if not r or r.project_id != project_id:
        raise HTTPException(404, "Round not found")
    return r


def _round_out(session: Session, r: BetaRound) -> RoundOut:
    readers = session.exec(select(BetaReader).where(BetaReader.round_id == r.id).order_by(BetaReader.invited_at)).all()
    counts: dict[str, int] = {}
    for c in session.exec(select(BetaComment.reader_id).where(BetaComment.round_id == r.id)).all():
        counts[c] = counts.get(c, 0) + 1
    return RoundOut(id=r.id, name=r.name, chapters=list(r.chapters), status=r.status,
                    created_at=r.created_at.isoformat(), closes_at=_iso(r.closes_at),
                    readers=[_reader_out(x, counts.get(x.id, 0)) for x in readers])


def _project_comment(session: Session, project_id: str, cid: str) -> tuple[BetaComment, BetaReader]:
    c = session.get(BetaComment, cid)
    if not c:
        raise HTTPException(404, "Comment not found")
    _round(session, project_id, c.round_id)
    return c, session.get(BetaReader, c.reader_id)


# ---- author: rounds & readers ---------------------------------------------------------

@router.get(P + "/rounds", response_model=list[RoundOut])
def list_rounds(project_id: str, session: Session = Depends(get_session)):
    _project(session, project_id)
    rows = session.exec(select(BetaRound).where(BetaRound.project_id == project_id)
                        .order_by(BetaRound.created_at.desc())).all()
    return [_round_out(session, r) for r in rows]


@router.post(P + "/rounds", response_model=RoundOut, status_code=201)
def create_round(project_id: str, body: RoundIn, session: Session = Depends(get_session)):
    _project(session, project_id)
    have = set(session.exec(select(Chapter.number).where(Chapter.project_id == project_id)).all())
    chapters = sorted({n for n in body.chapters if n in have})
    if not chapters:
        raise HTTPException(400, "Pick at least one existing chapter")
    r = BetaRound(project_id=project_id, name=body.name.strip(), chapters=chapters, closes_at=body.closes_at)
    session.add(r)
    session.commit()
    session.refresh(r)
    events.publish(project_id, "beta.updated", {"round": r.id})
    return _round_out(session, r)


@router.post(P + "/rounds/{rid}/close", response_model=RoundOut)
def close_round(project_id: str, rid: str, session: Session = Depends(get_session)):
    r = _round(session, project_id, rid)
    r.status = "closed"
    session.add(r)
    session.commit()
    session.refresh(r)
    events.publish(project_id, "beta.updated", {"round": r.id})
    return _round_out(session, r)


@router.post(P + "/rounds/{rid}/readers", response_model=ReaderOut, status_code=201)
def add_reader(project_id: str, rid: str, body: ReaderIn, session: Session = Depends(get_session)):
    r = _round(session, project_id, rid)
    x = BetaReader(round_id=r.id, name=body.name.strip(), email=(body.email or "").strip() or None,
                   token=secrets.token_urlsafe(24))
    session.add(x)
    session.commit()
    session.refresh(x)
    events.publish(project_id, "beta.updated", {"round": r.id})
    return _reader_out(x)


@router.delete(P + "/readers/{reader_id}", status_code=204)
def remove_reader(project_id: str, reader_id: str, session: Session = Depends(get_session)):
    x = session.get(BetaReader, reader_id)
    if not x:
        raise HTTPException(404, "Reader not found")
    _round(session, project_id, x.round_id)
    for c in session.exec(select(BetaComment).where(BetaComment.reader_id == x.id)).all():
        session.delete(c)
    for p in session.exec(select(BetaProgress).where(BetaProgress.reader_id == x.id)).all():
        session.delete(p)
    session.delete(x)
    session.commit()
    events.publish(project_id, "beta.updated", {"reader": reader_id})


# ---- author: comments ---------------------------------------------------------------

@router.get(P + "/comments", response_model=list[CommentOut])
def list_comments(project_id: str, round_id: Optional[str] = None, chapter: Optional[int] = None,
                  reader_id: Optional[str] = None, reaction: Optional[str] = None,
                  resolved: Optional[bool] = None, session: Session = Depends(get_session)):
    _project(session, project_id)
    q = (select(BetaComment, BetaReader.name).join(BetaReader, BetaReader.id == BetaComment.reader_id)
         .join(BetaRound, BetaRound.id == BetaComment.round_id).where(BetaRound.project_id == project_id))
    if round_id:
        q = q.where(BetaComment.round_id == round_id)
    if chapter is not None:
        q = q.where(BetaComment.chapter == chapter)
    if reader_id:
        q = q.where(BetaComment.reader_id == reader_id)
    if reaction:
        q = q.where(BetaComment.reaction == reaction)
    if resolved is not None:
        q = q.where(BetaComment.resolved == resolved)
    rows = session.exec(q.order_by(BetaComment.chapter, BetaComment.from_offset, BetaComment.created_at)).all()
    return [_comment_out(c, name) for c, name in rows]


@router.post(P + "/comments/{cid}/resolve", response_model=CommentOut)
def resolve_comment(project_id: str, cid: str, session: Session = Depends(get_session)):
    c, reader = _project_comment(session, project_id, cid)
    c.resolved = not c.resolved
    session.add(c)
    session.commit()
    session.refresh(c)
    events.publish(project_id, "beta.updated", {"comment": c.id})
    return _comment_out(c, reader.name if reader else "")


@router.post(P + "/comments/{cid}/to-memory")
def comment_to_memory(project_id: str, cid: str, body: ToMemoryIn | None = None,
                      session: Session = Depends(get_session)):
    c, reader = _project_comment(session, project_id, cid)
    binding = bool(body and body.binding)
    text = c.body.strip() or (f"reacted '{c.reaction}'" if c.reaction != "none" else "")
    if c.quote:
        text = f'"{c.quote[:300]}": {text}' if text else f'"{c.quote[:300]}"'
    content = f"Beta reader {reader.name if reader else 'a reader'} on ch {c.chapter}: {text}"
    # Non-binding taste hint by default; "decision" only when the author says it's a ruling.
    m = mem.remember(session, project_id, kind="decision" if binding else "style", content=content,
                     chapter=c.chapter, source=f"beta:{c.id}", importance=0.7 if binding else 0.5)
    events.publish(project_id, "memory.created", {"id": m.id})
    return {"id": m.id, "kind": m.kind, "content": m.content}


@router.post(P + "/summarize", status_code=202)
def summarize(project_id: str, round_id: Optional[str] = None, session: Session = Depends(get_session)):
    _project(session, project_id)
    if round_id:
        _round(session, project_id, round_id)
    try:
        run = summ.submit(project_id, round_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"run_id": run.id}


# ---- author: insights -------------------------------------------------------------

@router.get(P + "/insights")
def insights(project_id: str, round_id: Optional[str] = None, session: Session = Depends(get_session)):
    _project(session, project_id)
    rounds = session.exec(select(BetaRound).where(BetaRound.project_id == project_id)).all()
    if round_id:
        rounds = [r for r in rounds if r.id == round_id]
        if not rounds:
            raise HTTPException(404, "Round not found")
    round_ids = [r.id for r in rounds]
    chapters = sorted({n for r in rounds for n in r.chapters})
    if not round_ids:
        return {"chapters": [], "readers": 0, "dropoff": [], "heat": [], "confused": [], "reading_time": []}
    reader_ids = list(session.exec(select(BetaReader.id).where(BetaReader.round_id.in_(round_ids))).all())
    progress = session.exec(select(BetaProgress).where(BetaProgress.reader_id.in_(reader_ids))).all() \
        if reader_ids else []
    comments = session.exec(select(BetaComment).where(BetaComment.round_id.in_(round_ids))).all()
    texts = {c.number: c.text for c in session.exec(select(Chapter).where(
        Chapter.project_id == project_id, Chapter.number.in_(chapters))).all()} if chapters else {}
    titles = {c.number: c.title for c in session.exec(select(Chapter).where(
        Chapter.project_id == project_id, Chapter.number.in_(chapters))).all()} if chapters else {}
    return {
        "chapters": [{"number": n, "title": titles.get(n, "")} for n in chapters],
        "readers": len(reader_ids),
        "dropoff": ins.dropoff(chapters, progress),
        "heat": ins.heat(chapters, texts, comments),
        "confused": ins.confused(comments),
        "reading_time": ins.reading_time(chapters, progress),
    }


# ---- public reader --------------------------------------------------------------------

def _reader(session: Session, token: str) -> tuple[BetaReader, BetaRound]:
    x = session.exec(select(BetaReader).where(BetaReader.token == token)).first() if token else None
    if not x:
        raise HTTPException(404, "This link isn't valid")
    r = session.get(BetaRound, x.round_id)
    if not r:
        raise HTTPException(404, "This link isn't valid")
    if r.status == "closed" or (r.closes_at and _aware(r.closes_at) <= now()):
        raise HTTPException(410, "This reading round has closed")
    return x, r


def _touch(session: Session, x: BetaReader) -> None:
    x.last_seen_at = now()
    session.add(x)


@router.get("/read/{token}")
def read_view(token: str, session: Session = Depends(get_session)):
    x, r = _reader(session, token)
    p = session.get(Project, r.project_id)
    chs = session.exec(select(Chapter).where(Chapter.project_id == r.project_id, Chapter.number.in_(r.chapters))
                       .order_by(Chapter.number)).all()
    comments = session.exec(select(BetaComment).where(BetaComment.reader_id == x.id)
                            .order_by(BetaComment.chapter, BetaComment.created_at)).all()
    progress = session.exec(select(BetaProgress).where(BetaProgress.reader_id == x.id)).all()
    _touch(session, x)
    session.commit()
    return {
        "book": {"title": p.title if p else "", "author": (p.author if p else "") or ""},
        "round": {"name": r.name, "closes_at": _iso(r.closes_at)},
        "reader": {"name": x.name, "furthest_chapter": x.furthest_chapter, "finished": x.finished},
        "chapters": [{"number": c.number, "title": c.title, "text": c.text} for c in chs],
        "comments": [_comment_out(c, x.name).model_dump(exclude={"reader_id", "round_id", "resolved"})
                     for c in comments],
        "progress": [{"chapter": g.chapter, "percent": g.percent, "seconds_read": g.seconds_read} for g in progress],
    }


@router.post("/read/{token}/comments", status_code=201)
def read_comment(token: str, body: CommentIn, session: Session = Depends(get_session)):
    x, r = _reader(session, token)
    if body.chapter not in r.chapters:
        raise HTTPException(400, "That chapter isn't part of this round")
    if body.reaction not in REACTIONS:
        raise HTTPException(400, "Unknown reaction")
    if not body.body.strip() and body.reaction == "none":
        raise HTTPException(400, "Write a note or pick a reaction")
    if not ratelimit.allow(token):
        raise HTTPException(429, "That's a lot of notes. Take a breather and try again later.")
    c = BetaComment(round_id=r.id, reader_id=x.id, chapter=body.chapter, quote=body.quote.strip(),
                    from_offset=body.from_offset, to_offset=body.to_offset, body=body.body.strip(),
                    reaction=body.reaction)
    session.add(c)
    _touch(session, x)
    session.commit()
    session.refresh(c)
    events.publish(r.project_id, "beta.updated", {"comment": c.id})
    return _comment_out(c, x.name).model_dump(exclude={"reader_id", "round_id", "resolved"})


@router.post("/read/{token}/progress")
def read_progress(token: str, body: ProgressIn, session: Session = Depends(get_session)):
    x, r = _reader(session, token)
    if body.chapter not in r.chapters:
        raise HTTPException(400, "That chapter isn't part of this round")
    g = session.exec(select(BetaProgress).where(BetaProgress.reader_id == x.id,
                                                BetaProgress.chapter == body.chapter)).first()
    if not g:
        g = BetaProgress(reader_id=x.id, chapter=body.chapter)
    g.percent = max(g.percent, body.percent)
    g.seconds_read += body.seconds
    g.updated_at = now()
    session.add(g)
    if body.percent > 0:
        x.furthest_chapter = max(x.furthest_chapter, body.chapter)
    if body.chapter == max(r.chapters) and g.percent >= ins.FINISHED_AT:
        x.finished = True
    _touch(session, x)
    session.commit()
    return {"chapter": g.chapter, "percent": g.percent, "seconds_read": g.seconds_read, "finished": x.finished}
