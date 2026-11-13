"""Voice Lab: writing samples, learned Voice DNA, draft matching and lift."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events, jobs
from ..db import get_session
from ..models import Chapter, Project, VoiceProfile, VoiceSample
from ..models.base import now
from ..voice import learn as learn_mod
from ..voice.analyze import compute_traits, match
from ..voice.ingest import clean, read_upload
from ..voice.learn import get_or_create_profile

router = APIRouter(tags=["voice"])


def _project(session: Session, pid: str) -> Project:
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _chapter(session: Session, pid: str, n: int) -> Chapter:
    ch = session.exec(select(Chapter).where(Chapter.project_id == pid, Chapter.number == n)).first()
    if not ch:
        raise HTTPException(404, f"Chapter {n} not found")
    return ch


class SampleOut(BaseModel):
    id: str
    title: str
    word_count: int
    source: str
    created_at: str
    excerpt: str


def _sample_out(s: VoiceSample) -> SampleOut:
    return SampleOut(id=s.id, title=s.title, word_count=s.word_count, source=s.source,
                     created_at=s.created_at.isoformat(), excerpt=" ".join(s.text.split())[:180])


class SampleIn(BaseModel):
    text: str = ""
    title: str = ""
    chapter: Optional[int] = None
    source: Optional[str] = None  # "chapter:<n>" also accepted


@router.get("/projects/{project_id}/voice/samples", response_model=list[SampleOut])
def list_samples(project_id: str, session: Session = Depends(get_session)):
    _project(session, project_id)
    rows = session.exec(select(VoiceSample).where(VoiceSample.project_id == project_id)
                        .order_by(VoiceSample.created_at.desc())).all()
    return [_sample_out(s) for s in rows]


@router.post("/projects/{project_id}/voice/samples", response_model=SampleOut, status_code=201)
async def add_sample(project_id: str, request: Request, session: Session = Depends(get_session)):
    """JSON {text, title} or {chapter: n} / {source: "chapter:n"}; or multipart with `file` (+ title)."""
    _project(session, project_id)
    ctype = request.headers.get("content-type", "")
    title, source = "", "upload"
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        title = str(form.get("title") or "")
        up = form.get("file")
        if up is not None and hasattr(up, "read"):
            try:
                text = read_upload(up.filename or "", await up.read())
            except ValueError as e:
                raise HTTPException(400, str(e))
            title = title or (up.filename or "Upload")
        else:
            text = clean(str(form.get("text") or ""))
            source = "paste"
    else:
        body = SampleIn(**(await request.json()))
        n = body.chapter
        if n is None and body.source and body.source.startswith("chapter:"):
            try:
                n = int(body.source.split(":", 1)[1])
            except ValueError:
                raise HTTPException(400, "source must be chapter:<n>")
        if n is not None:
            ch = _chapter(session, project_id, n)
            text, source = clean(ch.text), f"chapter:{n}"
            title = body.title or f"Chapter {n}" + (f": {ch.title}" if ch.title else "")
        else:
            text, title, source = clean(body.text), body.title, "paste"
    if not text.strip():
        raise HTTPException(400, "Sample is empty")
    words = len(text.split())
    sample = VoiceSample(project_id=project_id, title=title or " ".join(text.split()[:6]),
                         text=text, word_count=words, source=source)
    session.add(sample)
    session.commit()
    session.refresh(sample)
    events.publish(project_id, "voice.updated", {"sample": sample.id})
    return _sample_out(sample)


@router.delete("/projects/{project_id}/voice/samples/{sample_id}", status_code=204)
def delete_sample(project_id: str, sample_id: str, session: Session = Depends(get_session)):
    s = session.get(VoiceSample, sample_id)
    if not s or s.project_id != project_id:
        raise HTTPException(404, "Sample not found")
    session.delete(s)
    session.commit()
    events.publish(project_id, "voice.updated", {"deleted": sample_id})


# --------------------------------------------------------------- profile

class ProfileOut(BaseModel):
    exists: bool
    traits: dict
    signature_moves: list
    never: list
    lift: str
    style_guide: str
    words_analyzed: int
    sample_count: int
    sample_words: int
    trait_rows: list = []
    updated_at: Optional[str] = None


def _profile_out(session: Session, pid: str) -> ProfileOut:
    prof = session.exec(select(VoiceProfile).where(VoiceProfile.project_id == pid)).first()
    samples = session.exec(select(VoiceSample.word_count).where(VoiceSample.project_id == pid)).all()
    if not prof:
        return ProfileOut(exists=False, traits={}, signature_moves=[], never=[], lift="me_plus_lift",
                          style_guide="", words_analyzed=0, sample_count=len(samples), sample_words=sum(samples))
    return ProfileOut(exists=bool(prof.traits), traits=prof.traits or {}, signature_moves=prof.signature_moves or [],
                      never=prof.never or [], lift=prof.lift, style_guide=prof.style_guide,
                      words_analyzed=prof.words_analyzed, sample_count=len(samples), sample_words=sum(samples),
                      trait_rows=match(prof.traits, prof.traits)["traits"] if prof.traits else [],
                      updated_at=prof.updated_at.isoformat())


@router.get("/projects/{project_id}/voice/profile", response_model=ProfileOut)
def get_profile(project_id: str, session: Session = Depends(get_session)):
    _project(session, project_id)
    return _profile_out(session, project_id)


class ProfilePatch(BaseModel):
    lift: Optional[Literal["pure_me", "me_plus_lift", "experiment"]] = None
    never: Optional[list[str]] = None
    style_guide: Optional[str] = None


@router.patch("/projects/{project_id}/voice/profile", response_model=ProfileOut)
def patch_profile(project_id: str, body: ProfilePatch, session: Session = Depends(get_session)):
    _project(session, project_id)
    prof = get_or_create_profile(session, project_id)
    if body.lift is not None:
        prof.lift = body.lift
    if body.never is not None:
        prof.never = [x.strip() for x in body.never if x.strip()]
    if body.style_guide is not None:
        prof.style_guide = body.style_guide.strip()
    prof.updated_at = now()
    session.add(prof)
    session.commit()
    events.publish(project_id, "voice.updated", {"lift": prof.lift})
    return _profile_out(session, project_id)


@router.post("/projects/{project_id}/voice/learn", status_code=202)
def learn_voice(project_id: str, session: Session = Depends(get_session)):
    _project(session, project_id)
    if not session.exec(select(VoiceSample.id).where(VoiceSample.project_id == project_id)).first():
        raise HTTPException(400, "Add at least one writing sample first.")
    run = jobs.submit(project_id, "voice", lambda rid: learn_mod.learn(project_id, rid))
    return {"run_id": run.id, "status": run.status}


# --------------------------------------------------------------- match

def _require_traits(session: Session, pid: str) -> tuple[dict, str]:
    prof = session.exec(select(VoiceProfile).where(VoiceProfile.project_id == pid)).first()
    if prof and prof.traits:
        return prof.traits, ""
    text, _ = learn_mod.combined_text(session, pid)
    if not text.strip():
        raise HTTPException(400, "Add writing samples first.")
    return compute_traits(text), ""


@router.get("/projects/{project_id}/voice/match")
def match_chapter(project_id: str, chapter: int, session: Session = Depends(get_session)):
    _project(session, project_id)
    you, _ = _require_traits(session, project_id)
    ch = _chapter(session, project_id, chapter)
    text = clean(ch.text)
    if not text.strip():
        raise HTTPException(400, f"Chapter {chapter} has no draft yet")
    result = match(you, compute_traits(text), who=ch.pov or "the POV character")
    return {"chapter": chapter, "title": ch.title, **result}


@router.get("/projects/{project_id}/voice/match/all")
def match_all(project_id: str, session: Session = Depends(get_session)):
    _project(session, project_id)
    you, _ = _require_traits(session, project_id)
    chapters = session.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.text != "")
                            .order_by(Chapter.number)).all()
    out = []
    for ch in chapters:
        text = clean(ch.text)
        if text.strip():
            out.append({"chapter": ch.number, "title": ch.title,
                        "score": match(you, compute_traits(text))["score"]})
    return out
