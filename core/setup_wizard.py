"""
Novel OS - Setup Wizard

Zero-friction onboarding. Detects whatever the user already has — the Claude Code
CLI, any provider API key, or a local model server — lets them pick, runs a live
connection test, and writes the choice to `.env`.

Run it with:

    python -m core.setup_wizard

Designed so the experience adapts to the user: a subscription holder is offered the
free Claude Code CLI; an API-key holder sees their key detected; a local user sees
their running server. No one has to memorize environment variables.
"""

from __future__ import annotations

import os
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Allow running both as `python -m core.setup_wizard` and `python core/setup_wizard.py`.
try:
    from .llm_client import LLMClient, LLMError, OPENAI_COMPAT_ALIASES
except ImportError:  # pragma: no cover - direct-script fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from llm_client import LLMClient, LLMError, OPENAI_COMPAT_ALIASES  # type: ignore


@dataclass
class Option:
    """A configurable provider the wizard discovered or can offer."""

    provider: str            # value for NOVEL_OS_LLM_PROVIDER
    label: str               # human-facing menu text
    recommended: bool = False
    needs_key: bool = False  # prompt the user to paste a key
    key_env: Optional[str] = None  # env var name to store a pasted key under
    model: Optional[str] = None    # NOVEL_OS_MODEL to record
    base_url: Optional[str] = None # NOVEL_OS_BASE_URL for custom endpoints


# Native, key-based providers we know how to detect.
NATIVE_KEYS = [
    ("anthropic", "ANTHROPIC_API_KEY", "Anthropic Claude (API key)"),
    ("openai", "OPENAI_API_KEY", "OpenAI (API key)"),
    ("gemini", "GEMINI_API_KEY", "Google Gemini (API key)"),
    ("gemini", "GOOGLE_API_KEY", "Google Gemini (API key)"),
]


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    """Quick liveness probe for a local model server."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_options(env: Optional[dict] = None) -> List[Option]:
    """Build a ranked list of available providers from the environment.

    Ordering: Claude Code CLI (free) first when present, then detected paid keys,
    then reachable local servers, then a manual entry catch-all.
    """
    env = os.environ if env is None else env
    options: List[Option] = []

    # 1. Claude Code CLI — free, subscription-backed, no key.
    if shutil.which("claude"):
        options.append(Option(
            provider="claude_cli",
            label="Claude Code CLI (free — uses your `claude` login / subscription)",
            recommended=True,
        ))

    # 2. Detected native API keys.
    seen = set()
    for provider, key_env, label in NATIVE_KEYS:
        if env.get(key_env) and (provider, key_env) not in seen:
            seen.add((provider, key_env))
            options.append(Option(provider=provider, label=f"{label} — {key_env} detected"))

    if env.get("AZURE_OPENAI_API_KEY") and env.get("AZURE_OPENAI_ENDPOINT"):
        options.append(Option(provider="azure", label="Azure OpenAI — credentials detected"))

    # 3. OpenAI-compatible aliases with a detected key.
    for alias, (_, _, key_env) in OPENAI_COMPAT_ALIASES.items():
        if env.get(key_env):
            options.append(Option(provider=alias, label=f"{alias} — {key_env} detected"))

    # 4. Reachable local servers.
    if _port_open("localhost", 11434):
        options.append(Option(provider="ollama", label="Ollama (running locally on :11434)"))
    if _port_open("localhost", 1234):
        options.append(Option(provider="lmstudio", label="LM Studio (running locally on :1234)"))

    # 5. Manual entry — always available.
    options.append(Option(
        provider="__manual__",
        label="Enter an API key / custom endpoint manually",
    ))
    return options


# --------------------------------------------------------------------------- .env

def write_env(updates: dict, env_path: Path, confirm=lambda msg: True) -> None:
    """Merge `updates` into the .env file, preserving unrelated lines.

    Existing keys that we're updating prompt via `confirm` before overwrite.
    """
    existing: dict = {}
    order: List[str] = []
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k not in existing:
                order.append(k)
            existing[k] = v.strip()

    for k, v in updates.items():
        if k in existing and existing[k] != v:
            if not confirm(f"{k} is already set to '{existing[k]}'. Overwrite with '{v}'?"):
                continue
        if k not in existing:
            order.append(k)
        existing[k] = v

    lines = [f"{k}={existing[k]}" for k in order]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- flow

def _smoke_test(provider: str, model: Optional[str], base_url: Optional[str],
                api_key: Optional[str]) -> Optional[str]:
    """Run a tiny live completion. Return None on success, or an error string."""
    try:
        client = LLMClient(provider=provider, model=model, base_url=base_url, api_key=api_key)
        reply = client.complete(
            system="You are a connection test. Reply with the single word: OK.",
            user="Reply with OK.",
        )
        if not reply.strip():
            return "Provider returned an empty response."
        return None
    except LLMError as e:
        return str(e)
    except Exception as e:  # pragma: no cover - provider SDKs raise varied types
        return f"{type(e).__name__}: {e}"


def run_wizard(env_path: Optional[Path] = None,
               input_fn=input, print_fn=print) -> int:
    """Interactive setup. Returns a process exit code (0 = success)."""
    env_path = env_path or (Path.cwd() / ".env")
    options = detect_options()

    print_fn("\n  Novel OS — setup\n  " + "-" * 30)
    print_fn("  Detecting what you already have...\n")
    for i, opt in enumerate(options, 1):
        tag = "  ★" if opt.recommended else "   "
        print_fn(f"{tag} {i}. {opt.label}")
    print_fn("")

    # Pick an option.
    while True:
        raw = input_fn(f"  Choose 1-{len(options)} [1]: ").strip() or "1"
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            chosen = options[int(raw) - 1]
            break
        print_fn("  Please enter a valid number.")

    api_key = None
    model = chosen.model
    base_url = chosen.base_url
    provider = chosen.provider

    if provider == "__manual__":
        provider = input_fn("  Provider name (e.g. openai, openai_compatible, ollama): ").strip()
        base_url = input_fn("  Base URL (blank for native providers): ").strip() or None
        api_key = input_fn("  API key (blank if not needed): ").strip() or None
        model = input_fn("  Model id (blank for provider default): ").strip() or None
    elif chosen.needs_key:
        api_key = input_fn("  Paste your API key: ").strip() or None

    print_fn("\n  Testing the connection...")
    err = _smoke_test(provider, model, base_url, api_key)
    if err:
        print_fn(f"  ✗ Connection test failed: {err}\n")
        return 1
    print_fn("  ✓ Connection works.\n")

    # Persist.
    updates = {"NOVEL_OS_LLM_PROVIDER": provider}
    if model:
        updates["NOVEL_OS_MODEL"] = model
    if base_url:
        updates["NOVEL_OS_BASE_URL"] = base_url
    if api_key:
        updates["NOVEL_OS_API_KEY"] = api_key

    def _confirm(msg: str) -> bool:
        return (input_fn(f"  {msg} [y/N]: ").strip().lower() or "n") == "y"

    write_env(updates, env_path, confirm=_confirm)
    print_fn(f"  Saved to {env_path}. You're ready — run the orchestrator to start writing.\n")
    return 0


def main() -> int:
    return run_wizard()


if __name__ == "__main__":
    raise SystemExit(main())
