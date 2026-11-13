"""Inline Editor suggestions: list, request, accept, dismiss."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events
from ..agents import memory as mem
from ..agents import suggest as sg
from ..db import get_session
from ..models import Chapter, ChapterVersion, Project
from ..models.base import now
from ..models.suggest_extra import Suggestion
from ..services import book as svc
from .book import ChapterOut, _agent_names, _row

router = APIRouter(tags=["suggestions"])
P = "/projects/{project_id}/chapters/{n}/suggestions"


class SuggestIn(BaseModel):
    focus: Optional[str] = ""


class SuggestionOut(BaseModel):
    id: str
    chapter: int
    run_id: Optional[str]
    quote: str
    replacement: str
    reason: str
    kind: str
    status: str
    created_at: str


def _out(x: Suggestion) -> SuggestionOut:
    return SuggestionOut(id=x.id, chapter=x.chapter, run_id=x.run_id, quote=x.quote, replacement=x.replacement,
                         reason=x.reason, kind=x.kind, status=x.status, created_at=x.created_at.isoformat())


def _chapter(session: Session, project_id: str, n: int) -> Chapter:
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    c = session.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == n)).first()
    if not c:
        raise HTTPException(404, "Chapter not found")
    return c


def _suggestion(session: Session, project_id: str, n: int, sid: str) -> Suggestion:
    x = session.get(Suggestion, sid)
    if not x or x.project_id != project_id or x.chapter != n:
        raise HTTPException(404, "Suggestion not found")
    return x


def _open(session: Session, project_id: str, n: int) -> list[Suggestion]:
    return list(session.exec(select(Suggestion).where(
        Suggestion.project_id == project_id, Suggestion.chapter == n, Suggestion.status == "open",
    ).order_by(Suggestion.created_at)).all())


def _apply(c: Chapter, x: Suggestion) -> bool:
    if x.quote not in c.text:
        return False
    c.text = c.text.replace(x.quote, x.replacement, 1)
    x.status = "accepted"
    return True


def _finish(session: Session, project_id: str, c: Chapter, accepted: int) -> ChapterOut:
    editor = sg.editor_agent(session, project_id)
    c.word_count = svc.word_count(c.text)
    c.doc = {}  # the editor rebuilds its document from the text (same as version restore)
    c.updated_at = now()
    session.add(c)
    session.add(ChapterVersion(chapter_id=c.id, kind="edit", text=c.text, word_count=c.word_count,
                               produced_by=f"agent:{editor.id}" if editor else "agent",
                               note="Accepted suggestion" if accepted == 1 else f"Accepted {accepted} suggestions"))
    session.commit()
    session.refresh(c)
    events.publish(project_id, "chapter.updated", {"number": c.number, "id": c.id, "suggestions_accepted": accepted})
    return _row(c, _agent_names(session, project_id), full=True)


@router.get(P, response_model=list[SuggestionOut])
def list_suggestions(project_id: str, n: int, session: Session = Depends(get_session)):
    _chapter(session, project_id, n)
    return [_out(x) for x in _open(session, project_id, n)]


@router.post(P, status_code=202)
def request_suggestions(project_id: str, n: int, body: SuggestIn | None = None,
                        session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    if not c.text.strip():
        raise HTTPException(400, "This chapter has no text yet")
    try:
        run = sg.suggest(project_id, n, (body.focus if body else "") or "")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"run_id": run.id}


@router.post(P + "/accept-all", response_model=ChapterOut)
def accept_all(project_id: str, n: int, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    accepted = 0
    for x in _open(session, project_id, n):
        if _apply(c, x):
            accepted += 1
            session.add(x)
    if not accepted:
        raise HTTPException(409, "None of the suggestions match the current text")
    return _finish(session, project_id, c, accepted)


@router.post(P + "/{sid}/accept", response_model=ChapterOut)
def accept(project_id: str, n: int, sid: str, session: Session = Depends(get_session)):
    c = _chapter(session, project_id, n)
    x = _suggestion(session, project_id, n, sid)
    if x.status != "open":
        raise HTTPException(409, f"Suggestion already {x.status}")
    if not _apply(c, x):
        raise HTTPException(409, "The quoted text has changed since this suggestion was made")
    session.add(x)
    return _finish(session, project_id, c, 1)


@router.post(P + "/{sid}/dismiss", response_model=SuggestionOut)
def dismiss(project_id: str, n: int, sid: str, session: Session = Depends(get_session)):
    _chapter(session, project_id, n)
    x = _suggestion(session, project_id, n, sid)
    x.status = "dismissed"
    session.add(x)
    session.commit()
    editor = sg.editor_agent(session, project_id)
    reason = f" ({x.reason})" if x.reason else ""
    # "style", not "preference": a rejected edit is a taste hint the Editor recalls,
    # not a binding author ruling (those are decisions/preferences/pins).
    mem.remember(session, project_id, kind="style", importance=0.4, chapter=n,
                 agent_id=editor.id if editor else None, source="suggestion",
                 content=f"Author rejected an edit: '{x.quote}' → '{x.replacement}'{reason}")
    session.refresh(x)
    events.publish(project_id, "chapter.updated", {"number": n, "suggestion_dismissed": sid})
    return _out(x)
