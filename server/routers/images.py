"""Image generation API: covers, portraits, maps, scenes. Results land in Media."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import events, imagegen, jobs
from ..db import get_session, session_scope
from ..models import CodexEntry, Connection, Project
from ..publish import media as media_lib

router = APIRouter(tags=["images"])

KINDS = ("cover", "portrait", "map", "image", "reference")
SYNC = False  # tests: run inline


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    provider: str = ""  # empty = first connected image provider
    model: str = ""
    aspect: str = "2:3"
    kind: str = "image"
    codex_entry_id: Optional[str] = None  # set as this entry's portrait when done


class PromptIn(BaseModel):
    kind: str = "cover"
    codex_entry_id: Optional[str] = None


def _connections(session: Session) -> dict[str, Connection]:
    return {c.provider: c for c in session.exec(select(Connection)).all() if c.provider in imagegen.PROVIDERS}


@router.get("/settings/image-providers")
def image_providers(session: Session = Depends(get_session)) -> list[dict]:
    conns = _connections(session)
    return [{
        "id": p.id, "label": p.label, "models": list(p.models), "default_model": p.default_model,
        "notes": p.notes, "connected": bool(conns.get(p.id) and conns[p.id].api_key),
    } for p in imagegen.PROVIDERS.values()]


@router.post("/projects/{project_id}/images/prompt")
def draft_prompt(project_id: str, body: PromptIn, session: Session = Depends(get_session)) -> dict:
    """A strong starting prompt from the book itself. Deterministic and instant; the author edits it."""
    p = session.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    bible = p.bible or {}
    setting = str(bible.get("setting") or bible.get("era") or "")
    if body.kind == "portrait" and body.codex_entry_id:
        e = session.get(CodexEntry, body.codex_entry_id)
        if not e or e.project_id != project_id:
            raise HTTPException(404, "Codex entry not found")
        facts = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in (e.facts or {}).items()
                          if k not in ("status", "died_chapter", "lost_chapter"))[:300]
        subject = {"character": "Portrait of", "location": "Painting of", "item": "Still life of"}.get(e.kind, "Illustration of")
        prompt = (f"{subject} {e.name}: {e.summary or ''} {facts}. "
                  f"Setting: {setting or p.genre or 'literary fiction'}. Painterly, quiet, natural light, "
                  "consistent character design, no text.").strip()
        return {"prompt": " ".join(prompt.split()), "aspect": "3:4" if e.kind == "character" else "3:2"}
    if body.kind == "map":
        return {"prompt": f"Hand-drawn map of the world of {p.title}. {setting} Muted ink and watercolour, "
                          "labelled places from the story, parchment texture.", "aspect": "3:2"}
    premise = (p.premise or "").strip()
    return {
        "prompt": (f"Book cover art for the {p.genre or 'literary'} novel \"{p.title}\". {premise} "
                   "One strong central image, generous negative space at the top for the title, "
                   "painterly, restrained palette, award-winning contemporary cover design, no text or lettering."),
        "aspect": "2:3",
    }


@router.post("/projects/{project_id}/images", status_code=202)
def generate_image(project_id: str, body: GenerateIn, session: Session = Depends(get_session)) -> dict:
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    conns = _connections(session)
    provider = body.provider or next((pid for pid in imagegen.PROVIDERS if conns.get(pid) and conns[pid].api_key), "")
    if not provider:
        raise HTTPException(400, "Connect an image service first (Google, OpenAI, Runway or Higgsfield) in Connections.")
    conn = conns.get(provider)
    if not conn or not conn.api_key:
        raise HTTPException(400, f"Add your {imagegen.PROVIDERS[provider].label} key in Connections first.")
    if body.codex_entry_id:
        e = session.get(CodexEntry, body.codex_entry_id)
        if not e or e.project_id != project_id:
            raise HTTPException(404, "Codex entry not found")
    kind = body.kind if body.kind in KINDS else "image"
    creds = {"api_key": conn.api_key, "base_url": conn.base_url or ""}
    model = body.model or (conn.default_model if conn.default_model in imagegen.PROVIDERS[provider].models else "")

    def work(run_id: str) -> dict:
        data = imagegen.generate(provider, body.prompt, aspect=body.aspect, model=model, **creds)
        with session_scope() as s:
            m, _ = media_lib.store(s, project_id, data, filename=f"{kind}-{run_id[:6]}.png",
                                   source="generated", kind=kind)
            m.caption = body.prompt[:300]
            m.tags = sorted(set((m.tags or []) + ["generated", provider]))
            s.add(m)
            if body.codex_entry_id:
                entry = s.get(CodexEntry, body.codex_entry_id)
                if entry:
                    entry.image_media_id = m.id
                    s.add(entry)
            s.commit()
            media_id = m.id
        events.publish(project_id, "publish.updated", {"media_id": media_id})
        if body.codex_entry_id:
            events.publish(project_id, "codex.updated", {"id": body.codex_entry_id})
        return {"media_id": media_id, "provider": provider, "model": model or imagegen.PROVIDERS[provider].default_model}

    if SYNC:
        return {"run_id": None, "status": "done", **work("inline")}
    run = jobs.submit(project_id, "image", work, input={"provider": provider, "kind": kind, "aspect": body.aspect})
    return {"run_id": run.id, "status": run.status, "provider": provider}
