"""Audiobook studio API: voice cast, pronunciations, chapter rendering, streaming, ACX check, export."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import events, jobs
from ..audio import pronounce, render, tts
from ..config import settings
from ..db import get_session, session_scope
from ..models import Chapter, CodexEntry, Connection, Project
from ..models.audio_extra import AudioCast, AudioTrack, Pronunciation

router = APIRouter(tags=["audio"])

SYNC = False  # tests: run inline


# --------------------------------------------------------------- helpers

def _key(session: Session, provider: str) -> str:
    conns = {c.provider: c for c in session.exec(select(Connection)).all()}
    for pid in tts.KEY_SOURCES.get(provider, ()):
        c = conns.get(pid)
        if c and c.api_key:
            return c.api_key
    return ""


def _project(session: Session, pid: str) -> Project:
    p = session.get(Project, pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _audio_dir(pid: str) -> Path:
    d = settings().media_dir / pid / "audio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cast(session: Session, pid: str) -> list[AudioCast]:
    return list(session.exec(select(AudioCast).where(AudioCast.project_id == pid)).all())


def _narrator(cast: list[AudioCast]) -> Optional[AudioCast]:
    return next((c for c in cast if c.codex_entry_id is None), None)


def _pairs(session: Session, pid: str) -> list[tuple[str, str]]:
    return [(p.term, p.say_as) for p in session.exec(select(Pronunciation).where(Pronunciation.project_id == pid))]


def _names(session: Session, cast: list[AudioCast]) -> dict[str, str]:
    """Lowercase names, first names and aliases of voiced characters -> cast id."""
    out: dict[str, str] = {}
    for c in cast:
        if not c.codex_entry_id or not c.voice:
            continue
        e = session.get(CodexEntry, c.codex_entry_id)
        if not e:
            continue
        for n in [e.name, *(e.aliases or [])]:
            n = (n or "").strip()
            if n:
                out.setdefault(n.lower(), c.id)
                out.setdefault(n.split()[0].lower(), c.id)
    return out


def _plan(session: Session, pid: str, text: str) -> tuple[list[tuple[AudioCast, str]], str]:
    """Voice segments for a chapter, plus a fingerprint of everything that affects the audio."""
    cast = _cast(session, pid)
    narrator = _narrator(cast)
    if not narrator or not narrator.provider or not narrator.voice:
        raise HTTPException(400, "Choose a narrator voice first.")
    by_id = {c.id: c for c in cast}
    pairs = _pairs(session, pid)
    # Attribute on the written names first, then respell for the voice.
    plan = [(by_id.get(k, narrator) if k else narrator, pronounce.apply(seg, pairs))
            for k, seg in render.segments(text, _names(session, cast))]
    fp = json.dumps([[c.provider, c.voice, c.style_instructions, s] for c, s in plan])
    return plan, render.text_sha(fp)


def _track_out(t: Optional[AudioTrack]) -> Optional[dict]:
    if not t:
        return None
    return {"id": t.id, "chapter": t.chapter, "provider": t.provider, "voice": t.voice,
            "duration_s": t.duration_s, "size": t.size, "created_at": t.created_at.isoformat(),
            "url": f"/api/audio/{t.id}"}


def _latest(session: Session, pid: str) -> dict[int, AudioTrack]:
    out: dict[int, AudioTrack] = {}
    for t in session.exec(select(AudioTrack).where(AudioTrack.project_id == pid).order_by(AudioTrack.created_at)):
        out[t.chapter] = t
    return out


# --------------------------------------------------------------- providers and voices

@router.get("/settings/audio-providers")
def audio_providers(session: Session = Depends(get_session)) -> list[dict]:
    return [{"id": p.id, "label": p.label, "default_model": p.default_model, "max_chars": p.max_chars,
             "connected": bool(_key(session, p.id))} for p in tts.PROVIDERS.values()]


@router.get("/audio/voices")
def voices(provider: str, session: Session = Depends(get_session)) -> list[dict]:
    if provider not in tts.PROVIDERS:
        raise HTTPException(404, "Unknown audio service")
    try:
        return tts.list_voices(provider, _key(session, provider))
    except tts.TTSError as e:
        raise HTTPException(502, str(e)) from e


# --------------------------------------------------------------- cast

class CastIn(BaseModel):
    codex_entry_id: Optional[str] = None
    provider: str = ""
    voice: str = ""
    style_instructions: str = Field(default="", max_length=1000)


@router.get("/projects/{pid}/audio/cast")
def get_cast(pid: str, session: Session = Depends(get_session)) -> list[dict]:
    """Narrator first, then every Codex character (with or without a voice yet)."""
    _project(session, pid)
    cast = _cast(session, pid)
    by_entry = {c.codex_entry_id: c for c in cast}
    rows = []

    def row(c: Optional[AudioCast], entry: Optional[CodexEntry]) -> dict:
        return {"id": c.id if c else None, "codex_entry_id": entry.id if entry else None,
                "name": entry.name if entry else "Narrator", "role": entry.role if entry else "narrator",
                "provider": c.provider if c else "", "voice": c.voice if c else "",
                "style_instructions": c.style_instructions if c else ""}

    rows.append(row(by_entry.get(None), None))
    chars = session.exec(select(CodexEntry).where(CodexEntry.project_id == pid, CodexEntry.kind == "character")
                         .order_by(CodexEntry.name)).all()
    for e in chars:
        rows.append(row(by_entry.get(e.id), e))
    return rows


@router.put("/projects/{pid}/audio/cast")
def put_cast(pid: str, body: CastIn, session: Session = Depends(get_session)) -> dict:
    _project(session, pid)
    if body.provider and body.provider not in tts.PROVIDERS:
        raise HTTPException(400, "Unknown audio service")
    if body.codex_entry_id:
        e = session.get(CodexEntry, body.codex_entry_id)
        if not e or e.project_id != pid:
            raise HTTPException(404, "Codex entry not found")
    c = next((c for c in _cast(session, pid) if c.codex_entry_id == body.codex_entry_id), None)
    c = c or AudioCast(project_id=pid, codex_entry_id=body.codex_entry_id)
    c.provider, c.voice, c.style_instructions = body.provider, body.voice, body.style_instructions
    session.add(c)
    session.commit()
    events.publish(pid, "audio.updated", {"cast": c.id})
    return {"id": c.id, "codex_entry_id": c.codex_entry_id, "provider": c.provider, "voice": c.voice,
            "style_instructions": c.style_instructions}


class SampleIn(BaseModel):
    provider: str
    voice: str
    style_instructions: str = ""
    text: str = ""


@router.post("/projects/{pid}/audio/sample")
def sample(pid: str, body: SampleIn, session: Session = Depends(get_session)) -> Response:
    """A one- or two-sentence voice preview. Not saved."""
    p = _project(session, pid)
    text = body.text.strip() or (f"This is {p.title}. The orchard was quiet that morning, "
                                 "and the glass leaves caught the first of the light.")
    sentences = re.split(r"(?<=[.!?])\s+", text)
    text = pronounce.apply(" ".join(sentences[:2])[:400], _pairs(session, pid))
    try:
        data = tts.synthesize(body.provider, text, voice=body.voice, style=body.style_instructions,
                              api_key=_key(session, body.provider))
    except tts.TTSError as e:
        raise HTTPException(400, str(e)) from e
    return Response(data, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


# --------------------------------------------------------------- pronunciations

class PronIn(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    say_as: str = Field(min_length=1, max_length=200)


@router.get("/projects/{pid}/audio/pronunciations")
def list_prons(pid: str, session: Session = Depends(get_session)) -> list[dict]:
    _project(session, pid)
    return [{"id": p.id, "term": p.term, "say_as": p.say_as} for p in
            session.exec(select(Pronunciation).where(Pronunciation.project_id == pid).order_by(Pronunciation.term))]


@router.post("/projects/{pid}/audio/pronunciations", status_code=201)
def add_pron(pid: str, body: PronIn, session: Session = Depends(get_session)) -> dict:
    _project(session, pid)
    existing = next((p for p in session.exec(select(Pronunciation).where(Pronunciation.project_id == pid))
                     if p.term.lower() == body.term.strip().lower()), None)
    p = existing or Pronunciation(project_id=pid, term=body.term.strip())
    p.say_as = body.say_as.strip()
    session.add(p)
    session.commit()
    events.publish(pid, "audio.updated", {"pronunciation": p.id})
    return {"id": p.id, "term": p.term, "say_as": p.say_as}


@router.delete("/projects/{pid}/audio/pronunciations/{rid}", status_code=204)
def delete_pron(pid: str, rid: str, session: Session = Depends(get_session)) -> Response:
    p = session.get(Pronunciation, rid)
    if not p or p.project_id != pid:
        raise HTTPException(404, "Not found")
    session.delete(p)
    session.commit()
    events.publish(pid, "audio.updated", {"pronunciation": rid})
    return Response(status_code=204)


@router.get("/projects/{pid}/audio/pronunciations/suggest")
def suggest_prons(pid: str, session: Session = Depends(get_session)) -> list[str]:
    _project(session, pid)
    names = [e.name for e in session.exec(select(CodexEntry).where(CodexEntry.project_id == pid))]
    return pronounce.suggest(names, [t for t, _ in _pairs(session, pid)])[:40]


# --------------------------------------------------------------- chapters and rendering

@router.get("/projects/{pid}/audio/chapters")
def audio_chapters(pid: str, session: Session = Depends(get_session)) -> list[dict]:
    _project(session, pid)
    latest = _latest(session, pid)
    rows = []
    for ch in session.exec(select(Chapter).where(Chapter.project_id == pid).order_by(Chapter.number)):
        t = latest.get(ch.number)
        rows.append({"number": ch.number, "title": ch.title, "word_count": ch.word_count,
                     "estimated_s": render.estimate_seconds(ch.text), "track": _track_out(t)})
    return rows


class RenderIn(BaseModel):
    force: bool = False


@router.post("/projects/{pid}/audio/chapters/{n}/render", status_code=202)
def render_chapter(pid: str, n: int, body: Optional[RenderIn] = None, session: Session = Depends(get_session)) -> dict:
    _project(session, pid)
    force = bool(body and body.force)
    ch = session.exec(select(Chapter).where(Chapter.project_id == pid, Chapter.number == n)).first()
    if not ch:
        raise HTTPException(404, "Chapter not found")
    if not (ch.text or "").strip():
        raise HTTPException(400, "This chapter has no text yet.")
    plan, sha = _plan(session, pid, ch.text)
    prev = _latest(session, pid).get(n)
    if prev and prev.text_sha == sha and Path(prev.path).exists() and not force:
        return {"run_id": None, "status": "skipped", "track": _track_out(prev)}
    keys = {c.provider: _key(session, c.provider) for c, _ in plan}
    missing = [p for p, k in keys.items() if not k]
    if missing:
        raise HTTPException(400, f"Connect {tts.PROVIDERS[missing[0]].label} in Connections first.")
    steps = [(c.provider, c.voice, c.style_instructions, s) for c, s in plan]

    def work(run_id: str) -> dict:
        parts = []
        for i, (prov, voice, style, seg) in enumerate(steps):
            if run_id != "inline":
                jobs.check(run_id)
            parts.append(tts.synthesize(prov, seg, voice=voice, style=style, api_key=keys[prov]))
            events.publish(pid, "run.progress", {"id": run_id, "done": i + 1, "total": len(steps)})
        data = b"".join(parts)
        path = _audio_dir(pid) / f"chapter-{n:03d}-{sha[:10]}.mp3"
        path.write_bytes(data)
        info = render.mp3_info(data)
        duration = info["duration_s"] or render.estimate_seconds(" ".join(s for *_, s in steps))
        with session_scope() as s:
            t = AudioTrack(project_id=pid, chapter=n, provider=steps[0][0], voice=steps[0][1],
                           duration_s=duration, size=len(data), path=str(path), text_sha=sha)
            s.add(t)
            s.flush()
            out = _track_out(t)
        events.publish(pid, "audio.updated", {"chapter": n})
        return {"track": out, "segments": len(steps)}

    if SYNC:
        return {"run_id": None, "status": "done", **work("inline")}
    run = jobs.submit(pid, "audio", work, chapter=n, input={"chapter": n, "segments": len(steps)})
    return {"run_id": run.id, "status": run.status}


@router.get("/audio/{track_id}")
def stream_track(track_id: str, request: Request, session: Session = Depends(get_session)) -> Response:
    t = session.get(AudioTrack, track_id)
    if not t or not Path(t.path).exists():
        raise HTTPException(404, "Track not found")
    # Track files are immutable (name includes the content hash), so cache hard.
    headers = {"Cache-Control": "private, max-age=31536000, immutable", "Accept-Ranges": "bytes"}
    size = Path(t.path).stat().st_size
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (request.headers.get("range") or "").strip())
    if not m or (not m.group(1) and not m.group(2)):
        # Older Starlette FileResponse ignores Range, so partial requests are handled below.
        return FileResponse(t.path, media_type="audio/mpeg", filename=f"chapter-{t.chapter:03d}.mp3",
                            content_disposition_type="inline", headers=headers)
    if m.group(1):
        start, end = int(m.group(1)), min(int(m.group(2) or size - 1), size - 1)
    else:  # suffix range: last N bytes
        start, end = max(0, size - int(m.group(2))), size - 1
    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    with open(t.path, "rb") as f:
        f.seek(start)
        data = f.read(end - start + 1)
    return Response(data, status_code=206, media_type="audio/mpeg",
                    headers={**headers, "Content-Range": f"bytes {start}-{end}/{size}"})


# --------------------------------------------------------------- ACX and export

@router.get("/projects/{pid}/audio/acx")
def acx(pid: str, measure: bool = True, session: Session = Depends(get_session)) -> dict:
    _project(session, pid)
    files = []
    for n, t in sorted(_latest(session, pid).items()):
        if not Path(t.path).exists():
            continue
        files.append({"chapter": n, "track_id": t.id, **render.acx_check(t.path, Path(t.path).read_bytes(), measure)})
    return {"files": files, "launch_checklist": render.LAUNCH_CHECKLIST}


@router.get("/projects/{pid}/audio/export")
def export(pid: str, session: Session = Depends(get_session)) -> Response:
    p = _project(session, pid)
    latest = _latest(session, pid)
    titles = {c.number: c.title for c in session.exec(select(Chapter).where(Chapter.project_id == pid))}
    buf = io.BytesIO()
    manifest = {"title": p.title, "chapters": []}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for n, t in sorted(latest.items()):
            if not Path(t.path).exists():
                continue
            name = f"{n:03d}.mp3"
            z.write(t.path, name)
            manifest["chapters"].append({"chapter": n, "title": titles.get(n, ""), "file": name,
                                         "duration_s": t.duration_s, "size": t.size, "provider": t.provider,
                                         "voice": t.voice})
        if not manifest["chapters"]:
            raise HTTPException(400, "Render a chapter first.")
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    slug = re.sub(r"[^a-z0-9]+", "-", (p.title or "audiobook").lower()).strip("-") or "audiobook"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{slug}-audiobook.zip"'})
