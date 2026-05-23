"""
Novel OS - Pluggable LLM Client

Supports any LLM provider via four backend types:

  - anthropic    Claude (anthropic SDK)
  - openai       Native OpenAI (openai SDK)
  - azure        Azure OpenAI (openai SDK, AzureOpenAI client)
  - gemini       Google Gemini (google-genai SDK)
  - openai_compatible  ANY endpoint that speaks OpenAI's /v1/chat/completions:
                       Kimi/Moonshot, Together, Groq, OpenRouter, DeepSeek,
                       Mistral, Fireworks, Ollama, vLLM, LM Studio, etc.

Convenience aliases (provider names that just preset openai_compatible's base_url):
  kimi, moonshot, groq, together, openrouter, deepseek, mistral, fireworks,
  ollama, lmstudio.

Configure via environment (or .env in project root):

  NOVEL_OS_LLM_PROVIDER    one of the names above (auto-detected if unset)
  NOVEL_OS_MODEL           model id / Azure deployment name
  NOVEL_OS_API_KEY         generic key for openai_compatible / aliases
  NOVEL_OS_BASE_URL        endpoint URL for 'openai_compatible'
  NOVEL_OS_MAX_TOKENS      int, default 8192

Provider-native keys also work as fallbacks:
  ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY / GOOGLE_API_KEY,
  KIMI_API_KEY / MOONSHOT_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY,
  OPENROUTER_API_KEY, DEEPSEEK_API_KEY, MISTRAL_API_KEY, FIREWORKS_API_KEY,
  AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_VERSION.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple


DEFAULT_MAX_TOKENS = 8192

# Convenience aliases -> (base_url, default_model, env_var_name for key)
OPENAI_COMPAT_ALIASES = {
    "kimi":       ("https://api.moonshot.ai/v1",      "kimi-k2-0905-preview",        "KIMI_API_KEY"),
    "moonshot":   ("https://api.moonshot.ai/v1",      "kimi-k2-0905-preview",        "MOONSHOT_API_KEY"),
    "groq":       ("https://api.groq.com/openai/v1",  "llama-3.3-70b-versatile",     "GROQ_API_KEY"),
    "together":   ("https://api.together.xyz/v1",     "meta-llama/Llama-3.3-70B-Instruct-Turbo", "TOGETHER_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1",    "anthropic/claude-3.5-sonnet", "OPENROUTER_API_KEY"),
    "deepseek":   ("https://api.deepseek.com/v1",     "deepseek-chat",               "DEEPSEEK_API_KEY"),
    "mistral":    ("https://api.mistral.ai/v1",       "mistral-large-latest",        "MISTRAL_API_KEY"),
    "fireworks":  ("https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct", "FIREWORKS_API_KEY"),
    "ollama":     ("http://localhost:11434/v1",       "llama3.2",                    "OLLAMA_API_KEY"),  # key usually ignored
    "lmstudio":   ("http://localhost:1234/v1",        "local-model",                 "LMSTUDIO_API_KEY"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct", "NVIDIA_API_KEY"),
}

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_AZURE_API_VERSION = "2024-10-21"


# --------------------------------------------------------------------------- .env

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


# --------------------------------------------------------------------------- client

class LLMClient:
    """Provider-agnostic LLM client.

    Resolution order when ``provider`` is None:
      1. NOVEL_OS_LLM_PROVIDER env var
      2. First provider whose native key is set, in this order:
         anthropic, openai, azure, gemini, then any openai_compatible alias.
    """

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

        # Map alias -> openai_compatible with preset base_url/model/key
        self._backend, self.model = self._build_backend(model)

    # ----- resolution

    @staticmethod
    def _resolve_provider() -> str:
        env_pick = os.environ.get("NOVEL_OS_LLM_PROVIDER")
        if env_pick:
            return env_pick
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            return "azure"
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini"
        for alias, (_, _, key_env) in OPENAI_COMPAT_ALIASES.items():
            if os.environ.get(key_env):
                return alias
        if os.environ.get("NOVEL_OS_API_KEY") and os.environ.get("NOVEL_OS_BASE_URL"):
            return "openai_compatible"
        raise LLMError(
            "No LLM provider configured. Set NOVEL_OS_LLM_PROVIDER and a key, or "
            "one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, AZURE_OPENAI_API_KEY, "
            "GEMINI_API_KEY, KIMI_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY, "
            "OPENROUTER_API_KEY, DEEPSEEK_API_KEY, MISTRAL_API_KEY, "
            "FIREWORKS_API_KEY, or NOVEL_OS_BASE_URL+NOVEL_OS_API_KEY."
        )

    def _build_backend(self, model: Optional[str]) -> Tuple[object, str]:
        name = self.provider_name
        env_model = os.environ.get("NOVEL_OS_MODEL")

        if name == "anthropic":
            return self._build_anthropic(), model or env_model or DEFAULT_ANTHROPIC_MODEL
        if name == "openai":
            return self._build_openai_native(), model or env_model or DEFAULT_OPENAI_MODEL
        if name == "azure":
            backend, deployment = self._build_azure(model or env_model)
            return backend, deployment
        if name == "gemini":
            return self._build_gemini(), model or env_model or DEFAULT_GEMINI_MODEL
        if name in OPENAI_COMPAT_ALIASES:
            base_url, default_model, key_env = OPENAI_COMPAT_ALIASES[name]
            key = self._explicit_api_key or os.environ.get(key_env) or os.environ.get("NOVEL_OS_API_KEY") or "not-needed"
            base_url = self._explicit_base_url or os.environ.get(f"{name.upper()}_BASE_URL", base_url)
            return self._build_openai_compatible(base_url, key), model or env_model or default_model
        if name == "openai_compatible":
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL")
            key = self._explicit_api_key or os.environ.get("NOVEL_OS_API_KEY") or "not-needed"
            if not base_url:
                raise LLMError("openai_compatible requires NOVEL_OS_BASE_URL (or base_url=).")
            if not (model or env_model):
                raise LLMError("openai_compatible requires NOVEL_OS_MODEL (or model=).")
            return self._build_openai_compatible(base_url, key), model or env_model
        raise LLMError(f"Unknown provider '{name}'.")

    # ----- backend builders

    def _build_anthropic(self):
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install anthropic") from e
        key = self._explicit_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        return anthropic.Anthropic(api_key=key)

    def _build_openai_native(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        key = self._explicit_api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY is not set.")
        return OpenAI(api_key=key)

    def _build_openai_compatible(self, base_url: str, api_key: str):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        return OpenAI(api_key=api_key, base_url=base_url)

    def _build_azure(self, deployment: Optional[str]):
        try:
            from openai import AzureOpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        key = self._explicit_api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
        if not (key and endpoint):
            raise LLMError("Azure needs AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")
        if not deployment:
            raise LLMError("Azure needs NOVEL_OS_MODEL set to the deployment name.")
        client = AzureOpenAI(api_key=key, api_version=api_version, azure_endpoint=endpoint)
        return client, deployment

    def _build_gemini(self):
        try:
            from google import genai  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install google-genai") from e
        key = self._explicit_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set.")
        return genai.Client(api_key=key)

    # ----- public API

    @property
    def provider(self) -> str:
        return self.provider_name

    def complete(self, system: str, user: str) -> str:
        """Single-turn message → assistant text."""
        if self.provider_name == "anthropic":
            return self._complete_anthropic(system, user)
        if self.provider_name == "gemini":
            return self._complete_gemini(system, user)
        # openai, azure, openai_compatible, and all aliases share the chat-completions shape
        return self._complete_openai_shape(system, user)

    def run_agent(self, agent_name: str, user: str, agents_dir: Optional[Path] = None) -> str:
        base = agents_dir or (Path(__file__).resolve().parent.parent / "agents")
        prompt_path = base / agent_name / "prompt.md"
        if not prompt_path.exists():
            raise LLMError(f"Agent prompt not found: {prompt_path}")
        return self.complete(prompt_path.read_text(encoding="utf-8"), user)

    # ----- backend completions

    def _complete_anthropic(self, system: str, user: str) -> str:
        resp = self._backend.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(b, "text", "") or "" for b in resp.content)

    def _complete_openai_shape(self, system: str, user: str) -> str:
        resp = self._backend.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def _complete_gemini(self, system: str, user: str) -> str:
        from google.genai import types  # type: ignore
        resp = self._backend.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=self.max_tokens,
            ),
        )
        return resp.text or ""
