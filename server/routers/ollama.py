"""Ollama model management for the Connections screen.

The pull route ends in ``/events`` so ``server/main.py`` skips gzip and the SSE stream isn't buffered.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from core import model_catalog

from .. import ollama_admin
from ..db import get_session
from ..models import Connection

router = APIRouter(prefix="/settings/ollama", tags=["ollama"])


def _conn(session: Session, provider: str) -> Optional[Connection]:
    return session.exec(select(Connection).where(Connection.provider == provider)).first()


def _local_base(session: Session) -> str:
    c = _conn(session, "ollama")
    return ollama_admin.resolve_base(c.base_url if c else None)


def _check(name: str) -> str:
    if not ollama_admin.valid_model(name):
        raise HTTPException(422, "Model names use letters, numbers and . _ : / - (up to 120 characters).")
    return name


class PullIn(BaseModel):
    model: str


@router.get("/models")
def installed(session: Session = Depends(get_session)) -> dict:
    return ollama_admin.list_installed(_local_base(session))


@router.post("/pull/events")
def pull(body: PullIn, session: Session = Depends(get_session)) -> StreamingResponse:
    model = _check(body.model.strip())
    base = _local_base(session)
    return StreamingResponse(
        ollama_admin.pull_events(base, model), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/models/{name:path}", status_code=204)
def delete(name: str, session: Session = Depends(get_session)):
    _check(name)
    try:
        ollama_admin.delete_model(_local_base(session), name)
    except ollama_admin.OllamaError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/library")
def library() -> dict:
    return {"note": "Suggestions, verify on ollama.com/library.", "models": ollama_admin.LIBRARY}


@router.get("/cloud-models")
def cloud_models(session: Session = Depends(get_session)) -> dict:
    c = _conn(session, "ollama_cloud")
    if not c or not c.api_key:
        return {"ok": False, "models": [], "error": "Add your Ollama API key (ollama.com/settings/keys).",
                "default_model": c.default_model if c else ""}
    res = model_catalog.list_models("ollama_cloud", api_key=c.api_key)
    error = res.get("error")
    if error:
        error = str(error).replace(c.api_key, "****")
    return {"ok": bool(res.get("ok")), "models": res.get("models", []), "error": error,
            "default_model": c.default_model, "connection_id": c.id}
