"""LLM gateway: every agent call goes through here.

Route resolution order:
  1. the Agent's own provider/model override (set per book in the Agent room)
  2. the studio RoleDefault for the agent's role (Settings > Agents)
  3. the default Connection (Settings > Connections)
  4. environment auto-detect inside core.llm_client (OLLAMA_API_KEY, ANTHROPIC_API_KEY, ...)
"""

from __future__ import annotations

import threading

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from core.llm_client import LLMClient, LLMError

from .models import Agent, Connection
from .models.settings_extra import RoleDefault

__all__ = ["Route", "resolve", "complete", "stream", "client_for", "route_for_connection", "LLMError"]

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


@dataclass(repr=False)
class Route:
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    source: str = ""  # agent | role | default
    temperature: Optional[float] = None

    def __repr__(self) -> str:  # never leak the key into logs
        return f"Route(provider={self.provider!r}, model={self.model!r}, source={self.source!r})"


def route_for_connection(c: Connection, model: str = "", source: str = "default") -> Route:
    return Route(c.provider, model or c.default_model, c.base_url, c.api_key, source)


def _route_for_provider(conns: dict[str, Connection], provider: str, model: str, source: str) -> Route:
    c = conns.get(provider)
    if c:
        return route_for_connection(c, model, source)
    return Route(provider, model, "", "", source)


def resolve(session: Session, agent: Optional[Agent] = None, role: Optional[str] = None) -> Optional[Route]:
    """Pick the route for an agent (or a bare role). None means 'let LLMClient auto-detect from env'."""
    conns = {c.provider: c for c in session.exec(select(Connection)).all()}
    if agent and agent.provider:
        r = _route_for_provider(conns, agent.provider, agent.model, "agent")
        r.temperature = agent.temperature
        return r
    role = role or (agent.role if agent else None)
    if role:
        rd = session.exec(select(RoleDefault).where(RoleDefault.role == role)).first()
        if rd and rd.provider:
            model = (agent.model if agent and agent.model else "") or rd.model
            r = _route_for_provider(conns, rd.provider, model, "role")
            r.temperature = rd.temperature
            return r
    default = next((c for c in conns.values() if c.is_default), None)
    if default:
        model = (agent.model if agent and agent.model else "") or default.default_model
        return route_for_connection(default, model, "default")
    return None


def client_for(route: Optional[Route], max_tokens: Optional[int] = None) -> LLMClient:
    if route is None:
        return LLMClient(max_tokens=max_tokens)
    kwargs: dict = {"provider": route.provider, "model": route.model or None, "max_tokens": max_tokens,
                    "temperature": route.temperature}
    if route.api_key:
        kwargs["api_key"] = route.api_key
    if route.base_url:
        base = route.base_url.rstrip("/")
        if route.provider == "ollama" and not base.endswith("/v1"):
            base += "/v1"
        kwargs["base_url"] = base
    return LLMClient(**kwargs)


def complete(session: Session, system: str, user: str, *, agent: Optional[Agent] = None,
             max_tokens: Optional[int] = None) -> tuple[str, Route | None, str]:
    """Run one completion. Returns (text, route, model_used)."""
    route = resolve(session, agent)
    client = client_for(route, max_tokens)
    text = client.complete(system=system, user=user)
    _usage.value = dict(client.last_usage) if client.last_usage else {}
    return text, route, client.model


_usage = threading.local()


def last_usage() -> dict:
    """Real token usage of this thread's most recent complete(): {"input", "output"}.
    Empty when the provider didn't report it (callers may then estimate)."""
    return dict(getattr(_usage, "value", {}) or {})


def stream(route: Optional[Route], system: str, user: str, *, max_tokens: Optional[int] = None) -> Iterator[str]:
    """Yield text chunks for a resolved route (used by the playground)."""
    client = client_for(route, max_tokens)
    yield from client.complete_stream(system=system, user=user)
