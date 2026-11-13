"""Settings: model connections, per-role routing and the streaming playground.

Keys are stored in the `connection` table and never returned: responses expose
`has_key` and the last four characters only.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import urllib.request
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from core import model_catalog
from core.llm_client import ollama_local_base

from .. import llm
from ..db import get_session
from ..models import Connection
from ..models.base import now
from ..models.settings_extra import RoleDefault

router = APIRouter(prefix="/settings", tags=["settings"])

ROLES = ["architect", "scribe", "editor", "guardian", "curator", "researcher"]

# --------------------------------------------------------------- provider catalogue

PROVIDERS: list[dict[str, Any]] = [
    {"id": "ollama_cloud", "label": "Ollama Cloud", "description": "Hosted open models on ollama.com.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://ollama.com/v1",
     "default_model": "gpt-oss:120b", "help_url": "https://ollama.com/settings/keys"},
    {"id": "ollama", "label": "Ollama (local)", "description": "Free and private, on this machine.",
     "fields": ["base_url", "default_model"], "needs_key": False, "default_base_url": "http://localhost:11434",
     "default_model": "llama3.2", "help_url": "https://ollama.com/download"},
    {"id": "claude_cli", "label": "Claude Code login", "description": "Uses your Claude subscription through the claude CLI.",
     "fields": ["default_model"], "needs_key": False, "default_base_url": "",
     "default_model": "", "help_url": "https://docs.claude.com/claude-code"},
    {"id": "anthropic", "label": "Anthropic", "description": "Claude models with an API key.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "",
     "default_model": "claude-sonnet-4-6", "help_url": "https://console.anthropic.com/settings/keys"},
    {"id": "openai", "label": "OpenAI", "description": "GPT models with an API key.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "",
     "default_model": "gpt-4o", "help_url": "https://platform.openai.com/api-keys"},
    {"id": "gemini", "label": "Google Gemini", "description": "Gemini models from Google AI Studio.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "",
     "default_model": "gemini-2.0-flash", "help_url": "https://aistudio.google.com/app/apikey"},
    {"id": "openrouter", "label": "OpenRouter", "description": "Hundreds of models behind one key.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://openrouter.ai/api/v1",
     "default_model": "anthropic/claude-3.5-sonnet", "help_url": "https://openrouter.ai/keys"},
    {"id": "groq", "label": "Groq", "description": "Very fast open models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.groq.com/openai/v1",
     "default_model": "llama-3.3-70b-versatile", "help_url": "https://console.groq.com/keys"},
    {"id": "deepseek", "label": "DeepSeek", "description": "DeepSeek chat and reasoning models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.deepseek.com/v1",
     "default_model": "deepseek-chat", "help_url": "https://platform.deepseek.com/api_keys"},
    {"id": "mistral", "label": "Mistral", "description": "Mistral's hosted models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.mistral.ai/v1",
     "default_model": "mistral-large-latest", "help_url": "https://console.mistral.ai/api-keys"},
    {"id": "azure", "label": "Azure OpenAI", "description": "OpenAI models deployed in your Azure subscription.",
     "fields": ["base_url", "api_key", "default_model"], "needs_key": True,
     "labels": {"base_url": "Endpoint", "default_model": "Deployment name"},
     "default_base_url": "https://YOUR-RESOURCE.openai.azure.com", "default_model": "",
     "help_url": "https://learn.microsoft.com/azure/ai-services/openai/quickstart"},
    {"id": "bedrock", "label": "AWS Bedrock", "description": "Claude on AWS, using your AWS credentials (env, profile or SSO).",
     "fields": ["base_url", "default_model"], "needs_key": False,
     "labels": {"base_url": "AWS region", "default_model": "Model id"},
     "default_base_url": "us-east-1", "default_model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
     "help_url": "https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html"},
    {"id": "xai", "label": "xAI Grok", "description": "Grok models from xAI.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.x.ai/v1",
     "default_model": "grok-4", "help_url": "https://console.x.ai"},
    {"id": "perplexity", "label": "Perplexity", "description": "Sonar models with live web search.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.perplexity.ai",
     "default_model": "sonar-pro", "help_url": "https://www.perplexity.ai/settings/api"},
    {"id": "together", "label": "Together AI", "description": "Open models, fast and cheap.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.together.xyz/v1",
     "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "help_url": "https://api.together.ai/settings/api-keys"},
    {"id": "fireworks", "label": "Fireworks", "description": "Hosted open models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.fireworks.ai/inference/v1",
     "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct", "help_url": "https://fireworks.ai/account/api-keys"},
    {"id": "nvidia", "label": "NVIDIA NIM", "description": "NVIDIA-hosted open models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://integrate.api.nvidia.com/v1",
     "default_model": "meta/llama-3.3-70b-instruct", "help_url": "https://build.nvidia.com"},
    {"id": "kimi", "label": "Kimi", "description": "Moonshot's Kimi models.",
     "fields": ["api_key", "default_model"], "needs_key": True, "default_base_url": "https://api.moonshot.ai/v1",
     "default_model": "kimi-k2-0905-preview", "help_url": "https://platform.moonshot.ai/console/api-keys"},
    {"id": "runway", "label": "Runway", "description": "Image generation for covers, portraits and scenes.",
     "fields": ["api_key"], "needs_key": True, "default_base_url": "", "capability": "images",
     "default_model": "gen4_image", "help_url": "https://dev.runwayml.com"},
    {"id": "google_flow", "label": "Google Flow (useapi.net)",
     "description": "Unofficial: generates images with your own Google Flow account through useapi.net. "
                    "Needs a useapi.net token and a Google AI plan; Google may rate-limit the account.",
     "fields": ["api_key", "base_url"], "needs_key": True, "default_base_url": "", "capability": "images",
     "labels": {"api_key": "useapi.net API token", "base_url": "Google account email (optional)"},
     "default_model": "nano-banana-2", "help_url": "https://useapi.net/docs/start-here/setup-google-flow"},
    {"id": "higgsfield", "label": "Higgsfield", "description": "Image generation (Soul models). Key as KEY_ID:KEY_SECRET.",
     "fields": ["api_key"], "needs_key": True, "default_base_url": "", "capability": "images",
     "labels": {"api_key": "Key ID:Secret"},
     "default_model": "higgsfield-ai/soul/v2/standard", "help_url": "https://cloud.higgsfield.ai"},
    {"id": "elevenlabs", "label": "ElevenLabs", "description": "Audiobook narration with ElevenLabs voices.",
     "fields": ["api_key"], "needs_key": True, "default_base_url": "", "capability": "audio",
     "default_model": "eleven_multilingual_v2", "help_url": "https://elevenlabs.io/app/settings/api-keys"},
    {"id": "openai_tts", "label": "OpenAI TTS", "description": "Audiobook narration only. Optional: your OpenAI "
     "connection already works for narration; add this to use a separate key.",
     "fields": ["api_key"], "needs_key": True, "default_base_url": "", "capability": "audio",
     "default_model": "gpt-4o-mini-tts", "help_url": "https://platform.openai.com/api-keys"},
    {"id": "lmstudio", "label": "LM Studio", "description": "A local server from LM Studio.",
     "fields": ["base_url", "default_model"], "needs_key": False, "default_base_url": "http://localhost:1234/v1",
     "default_model": "local-model", "help_url": "https://lmstudio.ai/docs/local-server"},
    {"id": "openai_compatible", "label": "Custom endpoint", "description": "Any OpenAI-compatible /v1 API.",
     "fields": ["base_url", "api_key", "default_model"], "needs_key": False, "default_base_url": "",
     "default_model": "", "help_url": "https://platform.openai.com/docs/api-reference/chat"},
]
PROVIDER_IDS = {p["id"] for p in PROVIDERS}
# Image-only and audio-only services (Runway, ElevenLabs...) can never be the default *writing* model.
IMAGE_ONLY = {p["id"] for p in PROVIDERS if p.get("capability") in ("images", "audio")}
_BY_ID = {p["id"]: p for p in PROVIDERS}


@router.get("/providers")
def providers() -> list[dict]:
    return PROVIDERS


# --------------------------------------------------------------- schemas

class ConnectionIn(BaseModel):
    provider: str
    label: str = ""
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    is_default: Optional[bool] = None


class ConnectionPatch(BaseModel):
    label: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None  # empty keeps the stored key
    default_model: Optional[str] = None


def out(c: Connection) -> dict:
    return {
        "id": c.id, "provider": c.provider, "label": c.label or _BY_ID.get(c.provider, {}).get("label", c.provider),
        "base_url": c.base_url, "default_model": c.default_model, "is_default": c.is_default,
        "has_key": bool(c.api_key), "key_last4": c.api_key[-4:] if len(c.api_key) >= 8 else "",
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# --------------------------------------------------------------- auto-detection

_probe_cache: dict[str, tuple[float, bool]] = {}


def _probe_local_ollama(base: str) -> bool:
    hit = _probe_cache.get(base)
    if hit and time.monotonic() - hit[0] < 30:
        return hit[1]
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=0.6):  # noqa: S310 - local probe
            ok = True
    except Exception:  # noqa: BLE001
        ok = False
    _probe_cache[base] = (time.monotonic(), ok)
    return ok


def _has_claude_cli() -> bool:
    return shutil.which("claude") is not None


def ensure_detected(session: Session) -> list[dict]:
    """Create an Ollama Cloud connection from OLLAMA_API_KEY, and return offers for
    local Ollama / Claude Code that the user can add with one click."""
    conns = {c.provider: c for c in session.exec(select(Connection)).all()}
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if key and "ollama_cloud" not in conns:
        c = Connection(provider="ollama_cloud", label="Ollama Cloud", base_url="",
                       api_key=key, default_model=_BY_ID["ollama_cloud"]["default_model"],
                       is_default=not any(x.is_default for x in conns.values()))
        session.add(c)
        session.commit()
        conns["ollama_cloud"] = c
    offers = []
    if "ollama" not in conns:
        base = ollama_local_base()
        if _probe_local_ollama(base):
            offers.append({"provider": "ollama", "label": "Ollama (local)", "base_url": base,
                           "reason": f"Ollama is answering on {base}."})
    if "claude_cli" not in conns and _has_claude_cli():
        offers.append({"provider": "claude_cli", "label": "Claude Code login", "base_url": "",
                       "reason": "The claude CLI is installed on this machine."})
    return offers


# --------------------------------------------------------------- connections CRUD

def _get(session: Session, cid: str) -> Connection:
    c = session.get(Connection, cid)
    if not c:
        raise HTTPException(404, "Connection not found")
    return c


@router.get("/connections")
def list_connections(session: Session = Depends(get_session)) -> dict:
    offers = ensure_detected(session)
    rows = session.exec(select(Connection).order_by(Connection.created_at)).all()
    return {"connections": [out(c) for c in rows], "detected": offers}


@router.post("/connections", status_code=201)
def create_connection(body: ConnectionIn, session: Session = Depends(get_session)) -> dict:
    if body.provider not in PROVIDER_IDS:
        raise HTTPException(422, f"Unknown provider '{body.provider}'")
    existing = session.exec(select(Connection).where(Connection.provider == body.provider)).first()
    if existing:  # one connection per provider: treat as update
        return update_connection(existing.id, ConnectionPatch(**body.model_dump(exclude={"provider", "is_default"})),
                                 session)
    has_default = session.exec(select(Connection).where(Connection.is_default == True)).first()  # noqa: E712
    c = Connection(provider=body.provider, label=body.label.strip(), base_url=body.base_url.strip(),
                   api_key=body.api_key.strip(), default_model=body.default_model.strip(),
                   is_default=body.provider not in IMAGE_ONLY and (bool(body.is_default) or not has_default))
    if c.is_default and has_default:
        for other in session.exec(select(Connection)).all():
            other.is_default = False
            session.add(other)
    session.add(c)
    session.commit()
    session.refresh(c)
    return out(c)


@router.patch("/connections/{cid}")
def update_connection(cid: str, body: ConnectionPatch, session: Session = Depends(get_session)) -> dict:
    c = _get(session, cid)
    if body.label is not None:
        c.label = body.label.strip()
    if body.base_url is not None:
        c.base_url = body.base_url.strip()
    if body.default_model is not None:
        c.default_model = body.default_model.strip()
    if body.api_key:  # empty keeps the existing key
        c.api_key = body.api_key.strip()
    session.add(c)
    session.commit()
    session.refresh(c)
    return out(c)


@router.delete("/connections/{cid}", status_code=204)
def delete_connection(cid: str, session: Session = Depends(get_session)):
    c = _get(session, cid)
    was_default = c.is_default
    session.delete(c)
    session.commit()
    if was_default:
        nxt = session.exec(select(Connection).where(Connection.provider.not_in(IMAGE_ONLY))
                           .order_by(Connection.created_at)).first()
        if nxt:
            nxt.is_default = True
            session.add(nxt)
            session.commit()


@router.post("/connections/{cid}/default")
def set_default(cid: str, session: Session = Depends(get_session)) -> dict:
    target = _get(session, cid)
    if target.provider in IMAGE_ONLY:
        raise HTTPException(400, f"{target.label or target.provider} makes images or audio, so it can't be the writing model.")
    for c in session.exec(select(Connection)).all():
        c.is_default = c.id == target.id
        session.add(c)
    session.commit()
    session.refresh(target)
    return out(target)


def _friendly(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if "401" in low or "unauthorized" in low or "invalid api key" in low or "authentication" in low:
        return "The key was refused. Check it and try again."
    if "connection" in low or "refused" in low or "timed out" in low:
        return "Couldn't reach the server. Is it running, and is the URL right?"
    if "404" in low or "not found" in low:
        return "The server answered but doesn't know that model."
    return msg[:240]


@router.post("/connections/{cid}/test")
def test_connection(cid: str, session: Session = Depends(get_session)) -> dict:
    c = _get(session, cid)
    route = llm.route_for_connection(c)
    t0 = time.perf_counter()
    try:
        client = llm.client_for(route, max_tokens=40)
        text = client.complete(system="You are a terse assistant.",
                               user="Say hello to a novelist in one short sentence.")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latency_ms": int((time.perf_counter() - t0) * 1000), "error": _friendly(e),
                "model": route.model}
    secs = max(time.perf_counter() - t0, 1e-3)
    words = text.strip().split()
    return {"ok": True, "latency_ms": int(secs * 1000), "model": client.model,
            "sample": " ".join(words[:12]), "tokens_per_s": round(max(len(text) / 4, 1) / secs, 1),
            "error": None}


@router.get("/connections/{cid}/models")
def connection_models(cid: str, session: Session = Depends(get_session)) -> dict:
    c = _get(session, cid)
    if c.provider == "claude_cli":
        models = [{"id": m} for m in ("sonnet", "opus", "haiku")]
        return {"ok": True, "provider": c.provider, "endpoint": "", "models": models, "error": None,
                "default_model": c.default_model}
    base = c.base_url or None
    if c.provider == "anthropic" or c.provider == "gemini":
        base = None
    res = model_catalog.list_models(c.provider, base_url=base, api_key=c.api_key or None)
    res["default_model"] = c.default_model
    return res


# --------------------------------------------------------------- per-role routing

class RoleIn(BaseModel):
    role: str
    provider: str = ""
    model: str = ""
    temperature: float = 0.7


def _role_out(role: str, rd: Optional[RoleDefault]) -> dict:
    return {"role": role, "provider": rd.provider if rd else "", "model": rd.model if rd else "",
            "temperature": rd.temperature if rd else 0.7}


@router.get("/roles")
def get_roles(session: Session = Depends(get_session)) -> list[dict]:
    rows = {r.role: r for r in session.exec(select(RoleDefault)).all()}
    return [_role_out(role, rows.get(role)) for role in ROLES]


@router.put("/roles")
def put_roles(body: list[RoleIn], session: Session = Depends(get_session)) -> list[dict]:
    for item in body:
        if item.role not in ROLES:
            raise HTTPException(422, f"Unknown role '{item.role}'")
        rd = session.exec(select(RoleDefault).where(RoleDefault.role == item.role)).first() \
            or RoleDefault(role=item.role)
        rd.provider = item.provider.strip()
        rd.model = item.model.strip()
        rd.temperature = min(max(item.temperature, 0.0), 2.0)
        rd.updated_at = now()
        session.add(rd)
    session.commit()
    return get_roles(session)


# --------------------------------------------------------------- playground (SSE)

SAMPLES = {
    "architect": "Outline, in three short beats, a chapter where a lighthouse keeper finds a letter.",
    "scribe": "Write the first paragraph of a chapter set in a rain-soaked orchard.",
    "editor": "Tighten this sentence: 'She walked slowly and carefully across the very old bridge.'",
    "guardian": "List two continuity risks when a character changes their name mid-book.",
    "curator": "Describe the voice of this line in one sentence: 'The sea kept its own counsel.'",
    "researcher": "Give two facts about how 19th-century lighthouses were lit.",
}


class PlaygroundIn(BaseModel):
    connection_id: Optional[str] = None
    provider: Optional[str] = None
    model: str = ""
    role: Optional[str] = None
    prompt: str = ""
    max_tokens: int = 300


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/playground")
def playground(body: PlaygroundIn, session: Session = Depends(get_session)) -> StreamingResponse:
    route: Optional[llm.Route]
    if body.connection_id:
        route = llm.route_for_connection(_get(session, body.connection_id), body.model, "playground")
    elif body.provider:
        c = session.exec(select(Connection).where(Connection.provider == body.provider)).first()
        route = llm.route_for_connection(c, body.model, "playground") if c else llm.Route(body.provider, body.model)
    else:
        route = llm.resolve(session, role=body.role)
    prompt = body.prompt.strip() or SAMPLES.get(body.role or "", SAMPLES["scribe"])
    system = f"You are the {body.role or 'scribe'} in a novel-writing studio. Be brief."
    max_tokens = min(max(body.max_tokens, 16), 1200)

    def gen():
        t0 = time.perf_counter()
        chars = 0
        try:
            for chunk in llm.stream(route, system, prompt, max_tokens=max_tokens):
                chars += len(chunk)
                yield _sse({"text": chunk})
        except Exception as e:  # noqa: BLE001
            yield _sse({"error": _friendly(e)})
            return
        secs = max(time.perf_counter() - t0, 1e-3)
        yield _sse({"done": True, "provider": route.provider if route else "auto",
                    "model": route.model if route else "", "latency_ms": int(secs * 1000),
                    "tokens_per_s": round(max(chars / 4, 1) / secs, 1)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
