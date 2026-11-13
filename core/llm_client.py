"""
Novel OS - Pluggable LLM Client

Supports any LLM provider via these backend types:

  - claude_cli   Claude Code CLI (no API key uses your `claude` login / subscription)
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

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterator, Optional, Tuple


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
    # Local Ollama needs no key; OLLAMA_HOST overrides the server (see _ollama_local_base).
    "ollama":     ("http://localhost:11434/v1",       "llama3.2",                    "OLLAMA_LOCAL_API_KEY"),
    # Ollama Cloud: same API, hosted at ollama.com, Bearer key from ollama.com/settings/keys.
    "ollama_cloud": ("https://ollama.com/v1",         "gpt-oss:120b",                "OLLAMA_API_KEY"),
    "lmstudio":   ("http://localhost:1234/v1",        "local-model",                 "LMSTUDIO_API_KEY"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct", "NVIDIA_API_KEY"),
    "xai":        ("https://api.x.ai/v1",             "grok-4",                      "XAI_API_KEY"),
    "perplexity": ("https://api.perplexity.ai",       "sonar-pro",                   "PERPLEXITY_API_KEY"),
}

def ollama_local_base() -> str:
    """Root URL of the local Ollama server, honouring OLLAMA_HOST like the ollama CLI does."""
    host = (os.environ.get("OLLAMA_HOST") or "http://localhost:11434").strip().rstrip("/")
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    if host.endswith("/v1"):
        host = host[:-3]
    return host


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
        temperature: Optional[float] = None,
    ):
        self.provider_name = (provider or self._resolve_provider()).lower()
        self.max_tokens = max_tokens or int(os.environ.get("NOVEL_OS_MAX_TOKENS", DEFAULT_MAX_TOKENS))
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        # None leaves each provider at its own default.
        self.temperature = temperature
        # Token usage of the most recent completion: {"input": int, "output": int}.
        self.last_usage: dict = {}

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
        # No paid key anywhere fall back to the Claude Code CLI if it's installed,
        # so subscription users get zero-config, zero-cost generation.
        if shutil.which("claude"):
            return "claude_cli"
        raise LLMError(
            "No LLM provider configured. Set NOVEL_OS_LLM_PROVIDER and a key, or "
            "one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, AZURE_OPENAI_API_KEY, "
            "GEMINI_API_KEY, KIMI_API_KEY, GROQ_API_KEY, TOGETHER_API_KEY, "
            "OPENROUTER_API_KEY, DEEPSEEK_API_KEY, MISTRAL_API_KEY, "
            "FIREWORKS_API_KEY, or NOVEL_OS_BASE_URL+NOVEL_OS_API_KEY. "
            "Or install the Claude Code CLI and run `claude login` (no API key needed), "
            "then run `python -m core.setup_wizard`."
        )

    def _build_backend(self, model: Optional[str]) -> Tuple[object, str]:
        name = self.provider_name
        env_model = os.environ.get("NOVEL_OS_MODEL")

        if name == "claude_cli":
            # No SDK/client to build; the backend is the `claude` CLI itself.
            # A model is optional if unset, the CLI uses its configured default.
            return self._build_claude_cli(), model or env_model or ""
        if name == "anthropic":
            return self._build_anthropic(), model or env_model or DEFAULT_ANTHROPIC_MODEL
        if name == "openai":
            return self._build_openai_native(), model or env_model or DEFAULT_OPENAI_MODEL
        if name == "azure":
            backend, deployment = self._build_azure(model or env_model)
            return backend, deployment
        if name == "gemini":
            return self._build_gemini(), model or env_model or DEFAULT_GEMINI_MODEL
        if name == "bedrock":
            if not (model or env_model):
                raise LLMError("Bedrock needs a model id, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0.")
            return self._build_bedrock(), model or env_model
        if name in OPENAI_COMPAT_ALIASES:
            base_url, default_model, key_env = OPENAI_COMPAT_ALIASES[name]
            key = self._explicit_api_key or os.environ.get(key_env) or os.environ.get("NOVEL_OS_API_KEY") or "not-needed"
            if name == "ollama":
                base_url = ollama_local_base() + "/v1"
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

    def _build_claude_cli(self) -> str:
        """Locate the Claude Code CLI. The 'backend' is just the path to the binary."""
        cli = shutil.which("claude")
        if not cli:
            raise LLMError(
                "The Claude Code CLI ('claude') was not found on PATH. Install it from "
                "https://docs.claude.com/claude-code, then run `claude login`."
            )
        return cli

    def _build_anthropic(self):
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install anthropic") from e
        key = self._explicit_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        kwargs = {"api_key": key}
        if self._explicit_base_url:
            kwargs["base_url"] = self._explicit_base_url
        return anthropic.Anthropic(**kwargs)

    def _build_openai_native(self):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        key = self._explicit_api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError("OPENAI_API_KEY is not set.")
        base = self._explicit_base_url or os.environ.get("OPENAI_BASE_URL")
        return OpenAI(api_key=key, base_url=base) if base else OpenAI(api_key=key)

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
        endpoint = self._explicit_base_url or os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
        if not (key and endpoint):
            raise LLMError("Azure needs AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")
        if not deployment:
            raise LLMError("Azure needs NOVEL_OS_MODEL set to the deployment name.")
        client = AzureOpenAI(api_key=key, api_version=api_version, azure_endpoint=endpoint)
        return client, deployment

    def _build_bedrock(self):
        """Claude on AWS Bedrock. Credentials come from the normal AWS chain
        (env vars, ~/.aws profile, SSO); the region from base_url or AWS_REGION."""
        try:
            from anthropic import AnthropicBedrock  # type: ignore
        except ImportError as e:
            raise LLMError('Install: pip install "anthropic[bedrock]"') from e
        region = (self._explicit_base_url or os.environ.get("AWS_REGION")
                  or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
        try:
            return AnthropicBedrock(aws_region=region)
        except Exception as e:  # botocore missing or bad config
            raise LLMError(f"AWS Bedrock isn't configured: {e}") from e

    def _build_gemini(self):
        try:
            from google import genai  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install google-genai") from e
        key = self._explicit_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set.")
        if self._explicit_base_url:
            from google.genai import types  # type: ignore
            return genai.Client(api_key=key, http_options=types.HttpOptions(base_url=self._explicit_base_url))
        return genai.Client(api_key=key)

    # ----- public API

    @property
    def provider(self) -> str:
        return self.provider_name

    def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        """Single-turn message → assistant text."""
        if max_tokens:
            saved, self.max_tokens = self.max_tokens, max_tokens
            try:
                return self.complete(system, user)
            finally:
                self.max_tokens = saved
        if self.provider_name == "claude_cli":
            return self._complete_claude_cli(system, user)
        if self.provider_name in ("anthropic", "bedrock"):
            return self._complete_anthropic(system, user)
        if self.provider_name == "gemini":
            return self._complete_gemini(system, user)
        # openai, azure, openai_compatible, and all aliases share the chat-completions shape
        return self._complete_openai_shape(system, user)

    def complete_stream(self, system: str, user: str, max_tokens: Optional[int] = None) -> Iterator[str]:
        """Yield text chunks as they arrive. Anthropic and every OpenAI-shaped backend
        stream natively; other backends yield the whole completion once."""
        limit = max_tokens or self.max_tokens
        if self.provider_name in ("anthropic", "bedrock"):
            with self._backend.messages.stream(
                model=self.model, max_tokens=limit, system=system,
                messages=[{"role": "user", "content": user}], **self._temperature_kw(),
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
            return
        if self.provider_name == "claude_cli":
            yield from self._stream_claude_cli(system, user)
            return
        if self.provider_name == "gemini":
            yield self.complete(system, user, max_tokens=limit)
            return
        stream = self._backend.chat.completions.create(
            model=self.model, max_tokens=limit, stream=True,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **self._temperature_kw(),
        )
        for event in stream:
            choices = getattr(event, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = getattr(delta, "content", None) if delta is not None else None
            if text:
                yield text

    def _temperature_kw(self) -> dict:
        return {} if self.temperature is None else {"temperature": float(self.temperature)}

    def run_agent(self, agent_name: str, user: str, agents_dir: Optional[Path] = None) -> str:
        base = agents_dir or (Path(__file__).resolve().parent.parent / "agents")
        prompt_path = base / agent_name / "prompt.md"
        if not prompt_path.exists():
            raise LLMError(f"Agent prompt not found: {prompt_path}")
        return self.complete(prompt_path.read_text(encoding="utf-8"), user)

    # ----- backend completions

    def _claude_cli_call(self, system: str, user: str, *, stream: bool) -> tuple[list, str]:
        """Command line and stdin prompt for the Claude Code CLI (print mode)."""
        cmd = [self._backend, "-p"]  # backend is the path to the claude binary
        if stream:
            cmd += ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
        else:
            cmd += ["--output-format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        # Fold the agent's system prompt into the message turn. Passing it via
        # --append-system-prompt buries the instruction beneath Claude Code's own
        # interactive base prompt, which makes the model ask for confirmation
        # instead of executing the task. Inlining the directive keeps it imperative.
        #
        # The preamble makes the CLI behave like a plain completion API: other
        # providers treat the system prompt as a standing order and just produce
        # the artifact; the `claude` CLI is interactive by default and will ask
        # clarifying questions unless told to act. This keeps behavior consistent.
        preamble = (
            "You are operating as a non-interactive text-generation engine, not a "
            "conversational assistant. Follow the ROLE and TASK below exactly and "
            "output ONLY the requested artifact (e.g. the prose, the outline, the "
            "JSON). Do not ask questions, do not add preamble, commentary, or "
            "meta-discussion. If information is missing, make reasonable creative "
            "choices and proceed.\n\n"
        )
        prompt = f"{preamble}# ROLE\n{system}\n\n# TASK / CONTEXT\n{user}" if system else user
        return cmd, prompt

    def _stream_claude_cli(self, system: str, user: str) -> Iterator[str]:
        """Stream text deltas from `claude -p --output-format stream-json --include-partial-messages`."""
        cmd, prompt = self._claude_cli_call(system, user, stream=True)
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8")
        except OSError as e:
            raise LLMError(f"Failed to invoke the Claude Code CLI: {e}") from e
        assert proc.stdin and proc.stdout
        proc.stdin.write(prompt)
        proc.stdin.close()
        streamed = False
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = evt.get("type")
            if kind == "stream_event":
                inner = evt.get("event") or {}
                delta = inner.get("delta") or {}
                if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        streamed = True
                        yield text
            elif kind == "result":
                usage = evt.get("usage") or {}
                self.last_usage = {
                    "input": int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0))
                    + int(usage.get("cache_creation_input_tokens", 0)),
                    "output": int(usage.get("output_tokens", 0)),
                }
                if evt.get("is_error"):
                    raise LLMError(f"Claude Code CLI error: {evt.get('result') or 'unknown'}")
                if not streamed and evt.get("result"):  # older CLIs without partial messages
                    yield evt["result"]
        if proc.wait() != 0 and not streamed:
            err = (proc.stderr.read() if proc.stderr else "").strip()
            raise LLMError(f"Claude Code CLI failed (exit {proc.returncode}): {err}")

    def _complete_claude_cli(self, system: str, user: str) -> str:
        """Run the prompt through the Claude Code CLI in non-interactive print mode.

        Uses the user's `claude` login (subscription): no API key, no per-token billing.
        The prompt is passed on stdin (not argv) to avoid length/quoting limits.
        """
        cmd, prompt = self._claude_cli_call(system, user, stream=False)
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except OSError as e:
            raise LLMError(f"Failed to invoke the Claude Code CLI: {e}") from e
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            hint = ""
            if "login" in stderr.lower() or "auth" in stderr.lower() or not stderr:
                hint = " you may need to run `claude login`."
            raise LLMError(f"Claude Code CLI failed (exit {proc.returncode}): {stderr}{hint}")
        out = (proc.stdout or "").strip()
        if not out:
            raise LLMError("Claude Code CLI returned no output.")
        try:
            data = json.loads(out)
        except json.JSONDecodeError as e:
            raise LLMError(f"Could not parse Claude Code CLI output as JSON: {e}") from e
        # The print-mode JSON envelope carries the assistant text in "result".
        text = data.get("result") if isinstance(data, dict) else None
        if not text:
            raise LLMError(f"Claude Code CLI JSON had no 'result' text: {out[:200]}")
        usage = data.get("usage") or {}
        self.last_usage = {
            "input": int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0))
            + int(usage.get("cache_creation_input_tokens", 0)),
            "output": int(usage.get("output_tokens", 0)),
        }
        return text

    def _complete_anthropic(self, system: str, user: str) -> str:
        resp = self._backend.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **self._temperature_kw(),
        )
        u = getattr(resp, "usage", None)
        self.last_usage = {"input": getattr(u, "input_tokens", 0) or 0, "output": getattr(u, "output_tokens", 0) or 0}
        return "".join(getattr(b, "text", "") or "" for b in resp.content)

    def _complete_openai_shape(self, system: str, user: str) -> str:
        resp = self._backend.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self._temperature_kw(),
        )
        u = getattr(resp, "usage", None)
        self.last_usage = {"input": getattr(u, "prompt_tokens", 0) or 0, "output": getattr(u, "completion_tokens", 0) or 0}
        return resp.choices[0].message.content or ""

    def _complete_gemini(self, system: str, user: str) -> str:
        from google.genai import types  # type: ignore
        resp = self._backend.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=self.max_tokens,
                **self._temperature_kw(),
            ),
        )
        u = getattr(resp, "usage_metadata", None)
        self.last_usage = {"input": getattr(u, "prompt_token_count", 0) or 0,
                           "output": getattr(u, "candidates_token_count", 0) or 0}
        return resp.text or ""
