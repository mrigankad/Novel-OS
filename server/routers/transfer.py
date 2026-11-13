"""Import a manuscript, back a book up, restore a backup."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from .. import events
from ..db import get_session
from ..importer.backup import RestoreError, build_backup, restore_backup
from ..importer.parse import MAX_BYTES, ImportError_, ParsedBook, parse_manuscript
from ..models import Chapter, ChapterVersion, Project
from .projects import _out, get_project

router = APIRouter(tags=["transfer"])

MAX_BACKUP_BYTES = 512 * 1024 * 1024


async def _read(file: UploadFile, limit: int, what: str) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"That {what} is over {limit // (1024 * 1024)} MB")
    return data


async def _parse(file: UploadFile) -> ParsedBook:
    data = await _read(file, MAX_BYTES, "file")
    try:
        return parse_manuscript(data, file.filename or "")
    except ImportError_ as e:
        raise HTTPException(400, str(e)) from e


@router.post("/projects/import/preview")
async def preview_import(file: UploadFile = File(...)):
    """Parse only: nothing is written."""
    return (await _parse(file)).report()


@router.post("/projects/import", status_code=201)
async def import_manuscript(file: UploadFile = File(...), title: Optional[str] = Form(None),
                            author: Optional[str] = Form(None), genre: Optional[str] = Form(None),
                            session: Session = Depends(get_session)):
    book = await _parse(file)
    p = Project(title=(title or "").strip() or book.title, author=(author or "").strip(),
                genre=(genre or "").strip(), status="revising")
    session.add(p)
    session.flush()
    for n, c in enumerate(book.chapters, 1):
        ch = Chapter(project_id=p.id, number=n, title=c.title, act=c.act, text=c.text, word_count=c.words,
                     status="drafted" if c.text.strip() else "planned", target_words=max(c.words, 1000))
        session.add(ch)
        session.flush()
        session.add(ChapterVersion(chapter_id=ch.id, kind="snapshot", text=c.text, word_count=c.words,
                                   note=f"Imported from {file.filename or 'manuscript'}"))
    session.commit()
    session.refresh(p)
    events.publish(p.id, "chapter.updated", {"imported": len(book.chapters)})
    return {"project": _out(session, p), "report": book.report()}


@router.get("/projects/{project_id}/backup")
def backup(project_id: str, session: Session = Depends(get_session)):
    p = get_project(session, project_id)
    data = build_backup(session, project_id)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", p.title).strip("-").lower() or "book"
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{slug}.novelos.zip"'})


@router.post("/projects/restore", status_code=201)
async def restore(file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = await _read(file, MAX_BACKUP_BYTES, "backup")
    try:
        p = restore_backup(session, data)
    except RestoreError as e:
        raise HTTPException(400, str(e)) from e
    return _out(session, p)
