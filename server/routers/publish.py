"""Cover studio, metadata vault, releases, compile and marketing kit."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import events, jobs
from ..db import get_session
from ..models import CoverDesign, Media, Project, Release
from ..models.base import now
from ..models.publish_extra import MarketingAsset
from ..publish import compile as compiler
from ..publish import cover as cv
from ..publish import has_pillow, has_reportlab, marketing
from ..publish import media as media_store
from ..publish.releases import STORES, get_metadata, overview
from .projects import get_project

router = APIRouter(tags=["publish"])


def _changed(project_id: str, what: str) -> None:
    events.publish(project_id, "publish.updated", {"what": what})


# ------------------------------------------------------------------ cover

def _spec(session: Session, project_id: str, fmt: str, trim: str, paper: str,
          pages: Optional[int]) -> cv.CoverSpec:
    try:
        return cv.compute_spec(fmt=fmt, trim=trim, paper=paper,
                               words=compiler.total_words(session, project_id), pages=pages)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/projects/{project_id}/cover/spec")
def cover_spec(project_id: str, format: str = "paperback", trim: str = "5.5x8.5", paper: str = "cream",
               pages: Optional[int] = None, session: Session = Depends(get_session)):
    get_project(session, project_id)
    spec = _spec(session, project_id, format, trim, paper, pages)
    d = spec.to_dict()
    d["spine_in"] = round(spec.spine_in, 3)
    d["back_copy_budget"] = cv.back_copy_budget(spec)
    d["template"] = "KDP + IngramSpark"
    return d


class CoverIn(BaseModel):
    format: str = "paperback"
    trim: str = "5.5x8.5"
    paper: str = "cream"
    pages: Optional[int] = None  # manual page override; stored in layout
    front_media_id: Optional[str] = None
    back_copy: str = ""
    spine_text: str = ""
    colors: dict = Field(default_factory=dict)
    layout: dict = Field(default_factory=dict)
    selected: bool = False


class CoverPatch(BaseModel):
    format: Optional[str] = None
    trim: Optional[str] = None
    paper: Optional[str] = None
    pages: Optional[int] = None
    front_media_id: Optional[str] = None
    back_copy: Optional[str] = None
    spine_text: Optional[str] = None
    colors: Optional[dict] = None
    layout: Optional[dict] = None
    selected: Optional[bool] = None
    clear_front: bool = False
    clear_pages: bool = False


def _cover_out(session: Session, c: CoverDesign) -> dict:
    d = c.model_dump(exclude={"created_at"})
    d["created_at"] = c.created_at.isoformat()
    d["pages"] = (c.layout or {}).get("pages")
    m = session.get(Media, c.front_media_id) if c.front_media_id else None
    d["front"] = {"id": m.id, "url": f"/api/media/{m.id}", "width": m.width, "height": m.height,
                  "content_type": m.content_type} if m else None
    return d


def _get_cover(session: Session, project_id: str, cover_id: str) -> CoverDesign:
    c = session.get(CoverDesign, cover_id)
    if not c or c.project_id != project_id:
        raise HTTPException(404, "Cover design not found")
    return c


def _check_media(session: Session, project_id: str, media_id: Optional[str]) -> None:
    if media_id:
        m = session.get(Media, media_id)
        if not m or m.project_id != project_id:
            raise HTTPException(422, "front_media_id is not an image in this project")


def _validate_cover(fmt: str, trim: str, paper: str) -> None:
    if fmt not in cv.FORMATS:
        raise HTTPException(422, f"format must be one of {', '.join(cv.FORMATS)}")
    if paper not in cv.PAPER:
        raise HTTPException(422, f"paper must be one of {', '.join(cv.PAPER)}")
    try:
        cv.parse_trim(trim)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _select_only(session: Session, project_id: str, keep: CoverDesign) -> None:
    for o in session.exec(select(CoverDesign).where(CoverDesign.project_id == project_id,
                                                    CoverDesign.selected == True,  # noqa: E712
                                                    CoverDesign.id != keep.id)).all():
        o.selected = False
        session.add(o)


@router.get("/projects/{project_id}/covers")
def list_covers(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    rows = session.exec(select(CoverDesign).where(CoverDesign.project_id == project_id)
                        .order_by(CoverDesign.created_at)).all()
    return [_cover_out(session, c) for c in rows]


@router.post("/projects/{project_id}/covers", status_code=201)
def create_cover(project_id: str, body: CoverIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    _validate_cover(body.format, body.trim, body.paper)
    _check_media(session, project_id, body.front_media_id)
    data = body.model_dump(exclude={"pages"})
    if body.pages:
        data["layout"] = {**data["layout"], "pages": body.pages}
    c = CoverDesign(project_id=project_id, **data)
    first = session.exec(select(CoverDesign.id).where(CoverDesign.project_id == project_id)).first() is None
    c.selected = c.selected or first
    session.add(c)
    if c.selected:
        _select_only(session, project_id, c)
    session.commit()
    session.refresh(c)
    _changed(project_id, "cover")
    return _cover_out(session, c)


@router.patch("/projects/{project_id}/covers/{cover_id}")
def update_cover(project_id: str, cover_id: str, body: CoverPatch, session: Session = Depends(get_session)):
    c = _get_cover(session, project_id, cover_id)
    data = body.model_dump(exclude_none=True, exclude={"clear_front", "clear_pages", "pages"})
    _validate_cover(data.get("format", c.format), data.get("trim", c.trim), data.get("paper", c.paper))
    _check_media(session, project_id, data.get("front_media_id"))
    for k, v in data.items():
        setattr(c, k, v)
    layout = dict(c.layout or {})
    if body.pages:
        layout["pages"] = body.pages
    if body.clear_pages:
        layout.pop("pages", None)
    c.layout = layout
    if body.clear_front:
        c.front_media_id = None
    if body.selected:
        _select_only(session, project_id, c)
    session.add(c)
    session.commit()
    session.refresh(c)
    _changed(project_id, "cover")
    return _cover_out(session, c)


@router.post("/projects/{project_id}/covers/{cover_id}/select")
def select_cover(project_id: str, cover_id: str, session: Session = Depends(get_session)):
    return update_cover(project_id, cover_id, CoverPatch(selected=True), session)


@router.delete("/projects/{project_id}/covers/{cover_id}", status_code=204)
def delete_cover(project_id: str, cover_id: str, session: Session = Depends(get_session)):
    c = _get_cover(session, project_id, cover_id)
    session.delete(c)
    session.commit()
    _changed(project_id, "cover")


def _cover_spec(session: Session, project_id: str, c: CoverDesign) -> cv.CoverSpec:
    return _spec(session, project_id, c.format, c.trim, c.paper, (c.layout or {}).get("pages"))


@router.get("/projects/{project_id}/covers/{cover_id}/preflight")
def cover_preflight(project_id: str, cover_id: str, session: Session = Depends(get_session)):
    p = get_project(session, project_id)
    c = _get_cover(session, project_id, cover_id)
    spec = _cover_spec(session, project_id, c)
    m = session.get(Media, c.front_media_id) if c.front_media_id else None
    img = {"width": m.width, "height": m.height, "content_type": m.content_type} if m else None
    checks = cv.preflight(spec, title=p.title, back_copy=c.back_copy, spine_text=c.spine_text, image=img)
    return {"spec": spec.to_dict(), "checks": checks,
            "ok": all(ch["status"] != "fail" for ch in checks)}


@router.get("/projects/{project_id}/covers/{cover_id}/export")
def export_cover(project_id: str, cover_id: str, kind: str = "pdf", session: Session = Depends(get_session)):
    """kind=pdf: print-ready full wrap. kind=jpg: ebook front 1600x2560 (or 2400x2400 for audiobook)."""
    p = get_project(session, project_id)
    c = _get_cover(session, project_id, cover_id)
    m = session.get(Media, c.front_media_id) if c.front_media_id else None
    path = media_store.file_path(m) if m and m.content_type != "image/svg+xml" else None
    slug = compiler.filename(p, "x").rsplit(".", 1)[0]
    if kind == "pdf":
        if not has_reportlab():
            raise HTTPException(501, "Print PDF needs reportlab: pip install reportlab")
        spec = _cover_spec(session, project_id, c)
        if spec.format not in ("paperback", "hardcover"):
            raise HTTPException(422, "Print PDF is for paperback or hardcover wraps.")
        data = cv.render_wrap_pdf(spec, title=p.title, author=p.author, back_copy=c.back_copy,
                                  spine_text=c.spine_text, image_path=str(path) if path and path.exists() else None,
                                  colors=c.colors or {})
        return Response(data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{slug}-cover-wrap.pdf"'})
    if kind == "jpg":
        if not has_pillow():
            raise HTTPException(501, "Ebook cover export needs Pillow: pip install Pillow")
        size = cv.AUDIO_PX if c.format == "audiobook" else cv.EBOOK_PX
        img = path.read_bytes() if path and path.exists() else None
        data = cv.render_ebook_jpeg(title=p.title, author=p.author, image_bytes=img, colors=c.colors or {},
                                    size=size)
        return Response(data, media_type="image/jpeg",
                        headers={"Content-Disposition": f'attachment; filename="{slug}-cover-{size[0]}x{size[1]}.jpg"'})
    raise HTTPException(422, "kind must be pdf or jpg")


@router.post("/projects/{project_id}/cover/concepts", status_code=202)
def cover_concepts(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    run = jobs.submit(project_id, "cover_concepts", marketing.generate_concepts(project_id))
    return {"run_id": run.id, "status": run.status}


@router.get("/projects/{project_id}/cover/concepts")
def list_concepts(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    return marketing.latest_concepts(session, project_id)


# ------------------------------------------------------------------ metadata

class MetadataIn(BaseModel):
    subtitle: str = ""
    series: str = ""
    series_number: Optional[int] = None
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    bisac: list[str] = Field(default_factory=list)
    isbn_ebook: str = ""
    isbn_print: str = ""
    language: str = "en"
    price: dict = Field(default_factory=dict)
    comps: list[str] = Field(default_factory=list)


def _meta_out(m) -> dict:
    d = m.model_dump(exclude={"updated_at"})
    d["updated_at"] = m.updated_at.isoformat()
    return d


def _clean_isbn(v: str) -> str:
    digits = "".join(ch for ch in v if ch.isdigit() or ch in "Xx")
    if digits and len(digits) not in (10, 13):
        raise HTTPException(422, "An ISBN has 10 or 13 digits.")
    return digits.upper()


@router.get("/projects/{project_id}/metadata")
def read_metadata(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    return _meta_out(get_metadata(session, project_id))


@router.put("/projects/{project_id}/metadata")
def write_metadata(project_id: str, body: MetadataIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    keywords = [k.strip() for k in body.keywords if k.strip()]
    if len(keywords) > 7:
        raise HTTPException(422, "Stores accept at most 7 keywords.")
    if any(len(k) > 50 for k in keywords):
        raise HTTPException(422, "Each keyword must be 50 characters or fewer.")
    m = get_metadata(session, project_id)
    data = body.model_dump()
    data["keywords"] = keywords
    data["bisac"] = [b.strip().upper() for b in body.bisac if b.strip()][:10]
    data["comps"] = [c.strip() for c in body.comps if c.strip()][:10]
    data["isbn_ebook"] = _clean_isbn(body.isbn_ebook)
    data["isbn_print"] = _clean_isbn(body.isbn_print)
    for k, v in data.items():
        setattr(m, k, v)
    m.updated_at = now()
    session.add(m)
    session.commit()
    session.refresh(m)
    _changed(project_id, "metadata")
    return _meta_out(m)


# ------------------------------------------------------------------ releases

class ReleasePatch(BaseModel):
    status: Optional[str] = None  # submitted | live | auto
    notes: Optional[str] = None
    checklist: Optional[dict[str, bool]] = None


@router.get("/projects/{project_id}/releases")
def list_releases(project_id: str, session: Session = Depends(get_session)):
    get_project(session, project_id)
    return overview(session, project_id)


@router.patch("/projects/{project_id}/releases/{store}")
def update_release(project_id: str, store: str, body: ReleasePatch, session: Session = Depends(get_session)):
    get_project(session, project_id)
    if store not in STORES:
        raise HTTPException(404, "Unknown store")
    overview(session, project_id)  # seeds rows
    r = session.exec(select(Release).where(Release.project_id == project_id, Release.store == store)).one()
    if body.status is not None:
        if body.status not in ("submitted", "live", "auto"):
            raise HTTPException(422, "status must be submitted, live or auto")
        r.status = "todo" if body.status == "auto" else body.status
    if body.notes is not None:
        r.notes = body.notes
    if body.checklist is not None:
        r.checklist = {**(r.checklist or {}), **body.checklist}
    r.updated_at = now()
    session.add(r)
    session.commit()
    _changed(project_id, "release")
    return next(x for x in overview(session, project_id)["releases"] if x["store"] == store)


# ------------------------------------------------------------------ compile

@router.get("/projects/{project_id}/compile")
def compile_book(project_id: str, format: str = "epub", session: Session = Depends(get_session)):
    p = get_project(session, project_id)
    if format not in compiler.FORMATS:
        raise HTTPException(422, f"format must be one of {', '.join(compiler.FORMATS)}")
    if format == "pdf" and not has_reportlab():
        raise HTTPException(501, "PDF export needs reportlab: pip install reportlab. EPUB and DOCX work without it.")
    data = compiler.render(session, p, format)
    return Response(data, media_type=compiler.CONTENT_TYPES[format],
                    headers={"Content-Disposition": f'attachment; filename="{compiler.filename(p, format)}"'})


# ------------------------------------------------------------------ marketing

class MarketingIn(BaseModel):
    kinds: list[str]


def _asset_out(a: MarketingAsset) -> dict:
    return {"id": a.id, "kind": a.kind, "content": a.content, "model": a.model,
            "created_at": a.created_at.isoformat()}


@router.post("/projects/{project_id}/marketing", status_code=202)
def run_marketing(project_id: str, body: MarketingIn, session: Session = Depends(get_session)):
    get_project(session, project_id)
    kinds = [k for k in dict.fromkeys(body.kinds)]
    bad = [k for k in kinds if k not in marketing.KINDS]
    if bad or not kinds:
        raise HTTPException(422, f"kinds must be from {', '.join(marketing.KINDS)}")
    run = jobs.submit(project_id, "marketing", marketing.generate_marketing(project_id, kinds),
                      input={"kinds": kinds})
    return {"run_id": run.id, "status": run.status, "kinds": kinds}


@router.get("/projects/{project_id}/marketing")
def list_marketing(project_id: str, kind: Optional[str] = None, session: Session = Depends(get_session)):
    get_project(session, project_id)
    q = select(MarketingAsset).where(MarketingAsset.project_id == project_id,
                                     MarketingAsset.kind != "cover_concepts")
    if kind:
        q = q.where(MarketingAsset.kind == kind)
    return [_asset_out(a) for a in session.exec(q.order_by(MarketingAsset.created_at.desc())).all()]


@router.delete("/projects/{project_id}/marketing/{asset_id}", status_code=204)
def delete_marketing(project_id: str, asset_id: str, session: Session = Depends(get_session)):
    a = session.get(MarketingAsset, asset_id)
    if not a or a.project_id != project_id:
        raise HTTPException(404, "Not found")
    session.delete(a)
    session.commit()
    _changed(project_id, "marketing")


@router.get("/projects/{project_id}/publish/capabilities")
def capabilities(project_id: str, session: Session = Depends(get_session)):
    p: Project = get_project(session, project_id)
    return {"pdf": has_reportlab(), "images": has_pillow(), "formats": list(compiler.FORMATS),
            "words": compiler.total_words(session, p.id), "marketing_kinds": list(marketing.KINDS)}
