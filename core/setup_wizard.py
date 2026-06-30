"""
Novel OS - Setup Wizard (local LLM only)

Detects LM Studio or Ollama on localhost, runs a live connection test, and writes
the choice to `.env`. No cloud providers, no Claude CLI, no external calls.

Run it with:

    python -m core.setup_wizard
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    from .llm_client import LLMClient, LLMError, LOCAL_OPENAI_ALIASES
except ImportError:  # pragma: no cover - direct-script fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from llm_client import LLMClient, LLMError, LOCAL_OPENAI_ALIASES  # type: ignore


@dataclass
class Option:
    """A local provider the wizard discovered or can offer."""

    provider: str
    label: str
    recommended: bool = False
    model: Optional[str] = None
    base_url: Optional[str] = None


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_options(env: Optional[dict] = None) -> List[Option]:
    """Build a list of reachable local model servers."""
    env = os.environ if env is None else env
    options: List[Option] = []

    if _port_open("127.0.0.1", 1234):
        url, default_model, _ = LOCAL_OPENAI_ALIASES["lmstudio"]
        options.append(Option(
            provider="lmstudio",
            label="LM Studio (localhost:1234)",
            recommended=True,
            model=env.get("NOVEL_OS_MODEL") or default_model,
            base_url=env.get("NOVEL_OS_BASE_URL") or url,
        ))

    if _port_open("127.0.0.1", 11434):
        url, default_model, _ = LOCAL_OPENAI_ALIASES["ollama"]
        options.append(Option(
            provider="ollama",
            label="Ollama (localhost:11434)",
            recommended=not options,
            model=env.get("NOVEL_OS_MODEL") or default_model,
            base_url=env.get("NOVEL_OS_BASE_URL") or url,
        ))

    options.append(Option(
        provider="__manual__",
        label="Enter a custom localhost endpoint manually",
    ))
    return options


def write_env(updates: dict, env_path: Path, confirm=lambda msg: True) -> None:
    """Merge `updates` into the .env file, preserving unrelated lines."""
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


def _smoke_test(provider: str, model: Optional[str], base_url: Optional[str],
                api_key: Optional[str]) -> Optional[str]:
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
    except Exception as e:  # pragma: no cover
        return f"{type(e).__name__}: {e}"


def run_wizard(env_path: Optional[Path] = None,
               input_fn=input, print_fn=print) -> int:
    env_path = env_path or (Path.cwd() / ".env")
    options = detect_options()

    print_fn("\n  Novel OS — local LLM setup\n  " + "-" * 30)
    print_fn("  Detecting local model servers on localhost...\n")
    for i, opt in enumerate(options, 1):
        tag = "  ★" if opt.recommended else "   "
        print_fn(f"{tag} {i}. {opt.label}")
    print_fn("")

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
        provider = input_fn("  Provider (lmstudio, ollama, or openai_compatible): ").strip()
        base_url = input_fn("  Base URL (must be localhost, e.g. http://127.0.0.1:1234/v1): ").strip() or None
        api_key = input_fn("  API key (blank if not needed): ").strip() or None
        model = input_fn("  Model id (blank for provider default): ").strip() or None

    print_fn("\n  Testing the connection...")
    err = _smoke_test(provider, model, base_url, api_key)
    if err:
        print_fn(f"  ✗ Connection test failed: {err}\n")
        return 1
    print_fn("  ✓ Connection works.\n")

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
