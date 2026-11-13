"""Media library: upload, import from URL, list, tag, serve, delete."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events
from ..db import get_session
from ..models import Media
from ..publish import media as store
from .projects import get_project

router = APIRouter(tags=["media"])


class MediaOut(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    sha256: str
    size: int
    width: int
    height: int
    kind: str
    caption: str
    tags: list
    source: str
    url: str
    created_at: str
    duplicate: bool = False


class MediaPatch(BaseModel):
    caption: Optional[str] = None
    tags: Optional[list[str]] = None
    kind: Optional[str] = None
    filename: Optional[str] = None


class ImportIn(BaseModel):
    url: str
    kind: str = "image"


def media_out(m: Media, duplicate: bool = False) -> MediaOut:
    return MediaOut(**m.model_dump(exclude={"created_at"}), url=f"/api/media/{m.id}",
                    created_at=m.created_at.isoformat(), duplicate=duplicate)


def _raise(e: store.MediaError):
    raise HTTPException(e.status, str(e))


@router.post("/projects/{project_id}/media", response_model=list[MediaOut], status_code=201)
async def upload_media(project_id: str, files: list[UploadFile] = File(...), kind: str = "image",
                       session: Session = Depends(get_session)):
    get_project(session, project_id)
    out = []
    for f in files:
        data = await f.read(store.MAX_BYTES + 1)
        try:
            m, created = store.store(session, project_id, data, filename=f.filename or "",
                                     declared=f.content_type or "", kind=kind)
        except store.MediaError as e:
            _raise(e)
        out.append(media_out(m, duplicate=not created))
    events.publish(project_id, "publish.updated", {"media": [m.id for m in out]})
    return out


@router.post("/projects/{project_id}/media/import", response_model=MediaOut, status_code=201)
def import_media(project_id: str, body: ImportIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    try:
        data, ctype, name = store.fetch_url(body.url)
        m, created = store.store(session, project_id, data, filename=name, declared=ctype,
                                 source="research" if body.kind == "reference" else "upload", kind=body.kind)
    except store.MediaError as e:
        _raise(e)
    events.publish(project_id, "publish.updated", {"media": [m.id]})
    return media_out(m, duplicate=not created)


@router.get("/projects/{project_id}/media", response_model=list[MediaOut])
def list_media(project_id: str, kind: Optional[str] = None, tag: Optional[str] = None,
               session: Session = Depends(get_session)):
    get_project(session, project_id)
    q = select(Media).where(Media.project_id == project_id)
    if kind:
        q = q.where(Media.kind == kind)
    rows = session.exec(q.order_by(Media.created_at.desc())).all()
    if tag:
        t = tag.lower()
        rows = [m for m in rows if t in (str(x).lower() for x in m.tags)]
    return [media_out(m) for m in rows]


def _get(session: Session, media_id: str) -> Media:
    m = session.get(Media, media_id)
    if not m:
        raise HTTPException(404, "Media not found")
    return m


@router.patch("/media/{media_id}", response_model=MediaOut)
def patch_media(media_id: str, body: MediaPatch, session: Session = Depends(get_session)):
    m = _get(session, media_id)
    data = body.model_dump(exclude_none=True)
    if "kind" in data and data["kind"] not in store.KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(store.KINDS)}")
    if "tags" in data:
        seen: list[str] = []
        for t in data["tags"]:
            t = t.strip()
            if t and t.lower() not in (x.lower() for x in seen):
                seen.append(t[:40])
        data["tags"] = seen[:20]
    for k, v in data.items():
        setattr(m, k, v)
    session.add(m)
    session.commit()
    session.refresh(m)
    events.publish(m.project_id, "publish.updated", {"media": [m.id]})
    return media_out(m)


# Same routes nested under the project, for symmetry with the list endpoint.
@router.patch("/projects/{project_id}/media/{media_id}", response_model=MediaOut)
def patch_project_media(project_id: str, media_id: str, body: MediaPatch, session: Session = Depends(get_session)):
    if _get(session, media_id).project_id != project_id:
        raise HTTPException(404, "Media not found")
    return patch_media(media_id, body, session)


@router.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: str, session: Session = Depends(get_session)):
    m = _get(session, media_id)
    pid = m.project_id
    store.remove(session, m)
    events.publish(pid, "publish.updated", {"media_deleted": media_id})


@router.delete("/projects/{project_id}/media/{media_id}", status_code=204)
def delete_project_media(project_id: str, media_id: str, session: Session = Depends(get_session)):
    if _get(session, media_id).project_id != project_id:
        raise HTTPException(404, "Media not found")
    delete_media(media_id, session)


@router.get("/media/{media_id}")
def serve_media(media_id: str, request: Request, session: Session = Depends(get_session)):
    m = _get(session, media_id)
    etag = f'"{m.sha256}"'
    headers = {"Cache-Control": "public, max-age=31536000, immutable", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    path = store.file_path(m)
    if not path.exists():
        raise HTTPException(410, "The file for this media is missing on disk.")
    if m.content_type == "image/svg+xml":  # SVG can carry script: sandbox it
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    headers["X-Content-Type-Options"] = "nosniff"
    return FileResponse(path, media_type=m.content_type, headers=headers)
