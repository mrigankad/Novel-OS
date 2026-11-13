"""The writers' room: chapter threads, direct threads, messages and quick-reply actions."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..agents import runtime
from ..db import get_session
from ..models import Message, Project, Thread

router = APIRouter(tags=["threads"])


class ThreadIn(BaseModel):
    title: str = ""
    kind: str = "direct"
    chapter: Optional[int] = None


class ThreadOut(BaseModel):
    id: str
    title: str
    chapter: Optional[int]
    kind: str
    updated_at: str


class MessageIn(BaseModel):
    body: str


class MessageOut(BaseModel):
    id: str
    thread_id: str
    sender: str
    recipients: list
    body: str
    intent: str
    actions: list
    run_id: Optional[str]
    created_at: str


def t_out(t: Thread) -> ThreadOut:
    return ThreadOut(id=t.id, title=t.title, chapter=t.chapter, kind=t.kind, updated_at=t.updated_at.isoformat())


def m_out(m: Message) -> MessageOut:
    return MessageOut(id=m.id, thread_id=m.thread_id, sender=m.sender, recipients=m.recipients or [], body=m.body,
                      intent=m.intent, actions=m.actions or [], run_id=m.run_id, created_at=m.created_at.isoformat())


def _thread(s: Session, pid: str, tid: str) -> Thread:
    t = s.get(Thread, tid)
    if not t or t.project_id != pid:
        raise HTTPException(404, "Thread not found")
    return t


@router.get("/projects/{pid}/threads", response_model=list[ThreadOut])
def list_threads(pid: str, s: Session = Depends(get_session)):
    return [t_out(t) for t in s.exec(select(Thread).where(Thread.project_id == pid)
                                     .order_by(Thread.updated_at.desc())).all()]


@router.post("/projects/{pid}/threads", response_model=ThreadOut, status_code=201)
def create_thread(pid: str, body: ThreadIn, s: Session = Depends(get_session)):
    if not s.get(Project, pid):
        raise HTTPException(404, "Project not found")
    if body.kind == "room" and body.chapter is not None:
        return t_out(runtime.chapter_thread(s, pid, body.chapter))
    t = Thread(project_id=pid, title=body.title or "Direct", kind=body.kind, chapter=body.chapter)
    s.add(t)
    s.commit()
    s.refresh(t)
    return t_out(t)


@router.get("/projects/{pid}/chapters/{n}/thread", response_model=ThreadOut)
def chapter_thread(pid: str, n: int, s: Session = Depends(get_session)):
    if not s.get(Project, pid):
        raise HTTPException(404, "Project not found")
    return t_out(runtime.chapter_thread(s, pid, n))


@router.get("/projects/{pid}/threads/{tid}/messages", response_model=list[MessageOut])
def list_messages(pid: str, tid: str, limit: int = 200, s: Session = Depends(get_session)):
    _thread(s, pid, tid)
    rows = s.exec(select(Message).where(Message.thread_id == tid).order_by(Message.created_at.desc())
                  .limit(min(limit, 500))).all()
    return [m_out(m) for m in reversed(rows)]


@router.post("/projects/{pid}/threads/{tid}/messages", status_code=201)
def post_message(pid: str, tid: str, body: MessageIn, s: Session = Depends(get_session)):
    """Author message. Every @mentioned agent replies (a chat run)."""
    t = _thread(s, pid, tid)
    if not body.body.strip():
        raise HTTPException(422, "body is required")
    msg, runs = runtime.author_message(s, pid, t, body.body.strip())
    return {"message": m_out(msg), "runs": [r.id for r in runs]}


@router.post("/projects/{pid}/threads/{tid}/messages/{mid}/actions/{action}")
def message_action(pid: str, tid: str, mid: str, action: str, s: Session = Depends(get_session)):
    _thread(s, pid, tid)
    m = s.get(Message, mid)
    if not m or m.thread_id != tid:
        raise HTTPException(404, "Message not found")
    try:
        return runtime.execute_action(s, pid, m, action)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
