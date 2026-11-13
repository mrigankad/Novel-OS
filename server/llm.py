"""LLM gateway: every agent call goes through here.

Resolves which provider/model to use (agent override -> studio default
Connection -> environment), calls core.llm_client, and records usage on the Run.
Streaming and per-agent routing UI are built on top of this (see routers/settings.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from core.llm_client import LLMClient, LLMError

from .models import Agent, Connection

__all__ = ["Route", "resolve", "complete", "LLMError"]

# Env var each provider reads its key from inside core.llm_client.
KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


@dataclass
class Route:
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""


def resolve(session: Session, agent: Optional[Agent] = None) -> Optional[Route]:
    """Pick the connection for an agent. None means 'let LLMClient auto-detect from env'."""
    conns = {c.provider: c for c in session.exec(select(Connection)).all()}
    if agent and agent.provider:
        c = conns.get(agent.provider)
        return Route(agent.provider, agent.model or (c.default_model if c else ""),
                     c.base_url if c else "", c.api_key if c else "")
    default = next((c for c in conns.values() if c.is_default), None)
    if default:
        model = (agent.model if agent and agent.model else "") or default.default_model
        return Route(default.provider, model, default.base_url, default.api_key)
    return None


def client_for(route: Optional[Route], max_tokens: Optional[int] = None) -> LLMClient:
    if route is None:
        return LLMClient(max_tokens=max_tokens)
    if route.provider == "ollama" and route.base_url:
        os.environ["OLLAMA_HOST"] = route.base_url
    kwargs = {"provider": route.provider, "model": route.model or None, "max_tokens": max_tokens}
    if route.api_key:
        kwargs["api_key"] = route.api_key
    if route.base_url and route.provider not in ("ollama",):
        kwargs["base_url"] = route.base_url
    return LLMClient(**kwargs)


def complete(session: Session, system: str, user: str, *, agent: Optional[Agent] = None,
             max_tokens: Optional[int] = None) -> tuple[str, Route | None, str]:
    """Run one completion. Returns (text, route, model_used)."""
    route = resolve(session, agent)
    client = client_for(route)
    text = client.complete(system=system, user=user, max_tokens=max_tokens) if max_tokens \
        else client.complete(system=system, user=user)
    return text, route, client.model
