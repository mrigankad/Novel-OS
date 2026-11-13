"""Projects (books) and the live event stream. Pattern for every other router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, func, select

from .. import events
from ..db import get_session
from ..models import Chapter, Project
from ..models.base import now

router = APIRouter(tags=["projects"])


class ProjectIn(BaseModel):
    title: str
    author: str = ""
    genre: str = ""
    premise: str = ""
    target_words: int = 90_000


class ProjectPatch(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    bible: Optional[dict] = None
    target_words: Optional[int] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    title: str
    author: str
    genre: str
    premise: str
    bible: dict
    status: str
    target_words: int
    word_count: int = 0
    chapter_count: int = 0
    updated_at: str


def get_project(session: Session, project_id: str) -> Project:
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _out(session: Session, p: Project) -> ProjectOut:
    words, count = session.exec(
        select(func.coalesce(func.sum(Chapter.word_count), 0), func.count(Chapter.id))
        .where(Chapter.project_id == p.id)
    ).one()
    return ProjectOut(**p.model_dump(exclude={"created_at", "updated_at"}),
                      word_count=int(words), chapter_count=int(count),
                      updated_at=p.updated_at.isoformat())


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)):
    rows = session.exec(select(Project).order_by(Project.updated_at.desc())).all()
    return [_out(session, p) for p in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)):
    p = Project(**body.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return _out(session, p)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(project_id: str, session: Session = Depends(get_session)):
    return _out(session, get_project(session, project_id))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectPatch, session: Session = Depends(get_session)):
    p = get_project(session, project_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    p.updated_at = now()
    session.add(p)
    session.commit()
    session.refresh(p)
    events.publish(project_id, "project.updated", {"id": project_id})
    return _out(session, p)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)):
    session.delete(get_project(session, project_id))
    session.commit()


@router.get("/projects/{project_id}/events")
async def project_events(project_id: str):
    """Server-Sent Events: run.updated, chapter.updated, message.created, memory.created..."""
    return StreamingResponse(events.stream(project_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
