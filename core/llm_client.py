"""
Novel OS - Local-only LLM Client

Calls exactly one endpoint: your configured local model server (LM Studio, Ollama,
or another OpenAI-compatible server on localhost). No cloud providers, no Claude CLI,
no auto-update checks, no telemetry.

Configure via environment (or .env in project root):

  NOVEL_OS_LLM_PROVIDER    lmstudio | ollama | openai_compatible
  NOVEL_OS_MODEL           model id loaded in your local server
  NOVEL_OS_BASE_URL        required for openai_compatible; must be localhost
  NOVEL_OS_API_KEY         optional key for local servers that require one
  NOVEL_OS_MAX_TOKENS      int, default 8192
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


DEFAULT_MAX_TOKENS = 8192

# Local OpenAI-compatible aliases only — no cloud preset URLs.
LOCAL_OPENAI_ALIASES = {
    "lmstudio": ("http://127.0.0.1:1234/v1", "local-model", "LMSTUDIO_API_KEY"),
    "ollama": ("http://127.0.0.1:11434/v1", "llama3.2", "OLLAMA_API_KEY"),
}

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _load_dotenv_if_present() -> None:
    """Load .env from cwd. Uses python-dotenv if installed, else a minimal parser."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv_if_present()


class LLMError(RuntimeError):
    """Raised when the LLM call cannot be made or fails."""


def assert_local_endpoint(base_url: str) -> None:
    """Reject any LLM endpoint that is not on localhost."""
    parsed = urlparse(base_url.strip())
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise LLMError(
            f"Blocked non-local LLM endpoint: {base_url!r}. "
            "Novel OS only calls your local model server "
            "(e.g. http://127.0.0.1:1234/v1 for LM Studio)."
        )


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class LLMClient:
    """Local-only LLM client."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider_name = (provider or self._resolve_provider()).lower()
        self.max_tokens = max_tokens or int(os.environ.get("NOVEL_OS_MAX_TOKENS", DEFAULT_MAX_TOKENS))
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        self._backend, self.model, self._base_url = self._build_backend(model)

    @staticmethod
    def _resolve_provider() -> str:
        env_pick = os.environ.get("NOVEL_OS_LLM_PROVIDER")
        if env_pick:
            return env_pick
        base_url = os.environ.get("NOVEL_OS_BASE_URL")
        if base_url:
            assert_local_endpoint(base_url)
            return "openai_compatible"
        if _port_open("127.0.0.1", 1234):
            return "lmstudio"
        if _port_open("127.0.0.1", 11434):
            return "ollama"
        raise LLMError(
            "No local LLM configured. Set NOVEL_OS_LLM_PROVIDER=lmstudio, "
            "NOVEL_OS_MODEL, and NOVEL_OS_BASE_URL=http://127.0.0.1:1234/v1 in .env, "
            "then start LM Studio's Local Server."
        )

    def _build_backend(self, model: Optional[str]) -> Tuple[object, str, str]:
        name = self.provider_name
        env_model = os.environ.get("NOVEL_OS_MODEL")

        if name in LOCAL_OPENAI_ALIASES:
            default_url, default_model, key_env = LOCAL_OPENAI_ALIASES[name]
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL", default_url)
            assert_local_endpoint(base_url)
            key = (
                self._explicit_api_key
                or os.environ.get(key_env)
                or os.environ.get("NOVEL_OS_API_KEY")
                or "not-needed"
            )
            return self._build_openai_compatible(base_url, key), model or env_model or default_model, base_url

        if name == "openai_compatible":
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL")
            key = self._explicit_api_key or os.environ.get("NOVEL_OS_API_KEY") or "not-needed"
            if not base_url:
                raise LLMError("openai_compatible requires NOVEL_OS_BASE_URL (localhost only).")
            assert_local_endpoint(base_url)
            if not (model or env_model):
                raise LLMError("openai_compatible requires NOVEL_OS_MODEL (or model=).")
            return self._build_openai_compatible(base_url, key), model or env_model, base_url

        raise LLMError(
            f"Unknown provider {name!r}. Allowed: lmstudio, ollama, openai_compatible "
            "(localhost endpoints only)."
        )

    def _build_openai_compatible(self, base_url: str, api_key: str):
        assert_local_endpoint(base_url)
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        return OpenAI(api_key=api_key, base_url=base_url)

    @property
    def provider(self) -> str:
        return self.provider_name

    @property
    def base_url(self) -> str:
        return self._base_url

    def complete(self, system: str, user: str, *, label: str = "") -> str:
        """Single-turn message → assistant text."""
        from app_settings import merge_system_prompt  # noqa: WPS433

        return self._complete_openai_shape(merge_system_prompt(system), user, label=label)

    def run_agent(self, agent_name: str, user: str, agents_dir: Optional[Path] = None) -> str:
        base = agents_dir or (Path(__file__).resolve().parent.parent / "agents")
        prompt_path = base / agent_name / "prompt.md"
        if not prompt_path.exists():
            raise LLMError(f"Agent prompt not found: {prompt_path}")
        from llm_call_context import format_timestamp, get_llm_job_label  # noqa: WPS433

        ctx = get_llm_job_label()
        agent_label = f"Agent:{agent_name}"
        call_label = f"{ctx} · {agent_label}" if ctx else f"App · {agent_label} · {format_timestamp()}"
        return self.complete(
            prompt_path.read_text(encoding="utf-8"),
            user,
            label=call_label,
        )

    def _complete_openai_shape(self, system: str, user: str, *, label: str = "") -> str:
        from llm_queue import QueueFlushedError, get_llm_queue  # noqa: WPS433

        try:
            with get_llm_queue().acquire(label):
                resp = self._backend.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
        except QueueFlushedError as e:
            raise LLMError(str(e)) from e
        return resp.choices[0].message.content or ""
