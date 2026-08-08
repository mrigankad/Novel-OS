"""Studio-level LLM settings (local product). Persists next to the DB / projects root."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

# Keys we are willing to set from the Studio UI into the process env.
_ENV_KEYS = (
    "NOVEL_OS_LLM_PROVIDER",
    "NOVEL_OS_MODEL",
    "NOVEL_OS_API_KEY",
    "NOVEL_OS_BASE_URL",
    "NOVEL_OS_MAX_TOKENS",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
)

PRESETS: dict[str, dict[str, str]] = {
    "quality": {
        "label": "Quality",
        "hint": "Best prose and planning (Claude / strong cloud).",
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "mature_capable": "false",
    },
    "fast": {
        "label": "Fast",
        "hint": "Cheaper / quicker drafts.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mature_capable": "false",
    },
    "local": {
        "label": "Local",
        "hint": "Ollama / LM Studio private, mature-capable if your model is.",
        "provider": "ollama",
        "model": "llama3.2",
        "mature_capable": "true",
    },
    "mature": {
        "label": "Mature-capable",
        "hint": "OpenRouter / uncensored routes. Not a hosted NSFW model.",
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "mature_capable": "true",
    },
}


def settings_path() -> Path:
    root = Path(os.environ.get("NOVEL_OS_SETTINGS_PATH", "./studio_settings.json"))
    return root


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def apply_to_environ(data: dict[str, Any]) -> None:
    """Push saved studio settings into process env (does not wipe unset keys)."""
    for key in _ENV_KEYS:
        val = data.get(key)
        if val is None or val == "":
            continue
        os.environ[key] = str(val)
    preset = data.get("preset")
    if preset and preset in PRESETS and not data.get("NOVEL_OS_LLM_PROVIDER"):
        p = PRESETS[preset]
        os.environ.setdefault("NOVEL_OS_LLM_PROVIDER", p["provider"])
        os.environ.setdefault("NOVEL_OS_MODEL", p["model"])


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    for k, v in patch.items():
        if v is None:
            current.pop(k, None)
        else:
            current[k] = v
    # Apply preset defaults when switching preset without overriding explicit model
    preset = current.get("preset")
    if preset in PRESETS:
        p = PRESETS[preset]
        if patch.get("preset") and not patch.get("NOVEL_OS_LLM_PROVIDER"):
            current["NOVEL_OS_LLM_PROVIDER"] = p["provider"]
        if patch.get("preset") and not patch.get("NOVEL_OS_MODEL"):
            current["NOVEL_OS_MODEL"] = p["model"]
        current["mature_capable"] = p["mature_capable"] == "true"
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    apply_to_environ(current)
    return current


def llm_status() -> dict[str, Any]:
    """Resolve current provider without raising (for Studio UI)."""
    from core.llm_client import LLMClient, LLMError

    saved = load_settings()
    apply_to_environ(saved)
    configured = True
    error: Optional[str] = None
    provider = os.environ.get("NOVEL_OS_LLM_PROVIDER") or ""
    model = os.environ.get("NOVEL_OS_MODEL") or ""
    try:
        client = LLMClient()
        provider = client.provider
        model = client.model
    except LLMError as e:
        configured = False
        error = str(e)
    except Exception as e:  # pragma: no cover defensive
        configured = False
        error = f"{type(e).__name__}: {e}"

    return {
        "configured": configured,
        "provider": provider,
        "model": model,
        "preset": saved.get("preset"),
        "mature_capable": bool(saved.get("mature_capable", False)),
        "error": error,
        "presets": [
            {
                "id": k,
                "label": v["label"],
                "hint": v["hint"],
                "provider": v["provider"],
                "model": v["model"],
                "mature_capable": v["mature_capable"] == "true",
            }
            for k, v in PRESETS.items()
        ],
        "onboarding_completed": bool(saved.get("onboarding_completed", False)),
    }
