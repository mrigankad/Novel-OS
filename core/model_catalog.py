"""
Novel OS - Model catalog

Lists the models a provider actually offers, so the Studio can show a picker
instead of asking writers to type model ids from memory.

- ollama        local server: GET {OLLAMA_HOST}/api/tags (no key)
- ollama_cloud  GET https://ollama.com/api/tags with Bearer OLLAMA_API_KEY
- anything OpenAI-compatible: GET {base_url}/models

Never raises for network problems: returns ``{"ok": False, "error": ...}`` so the
UI can say "Ollama isn't running" rather than crash.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from core.llm_client import OPENAI_COMPAT_ALIASES, ollama_local_base

OLLAMA_CLOUD_ROOT = "https://ollama.com"
TIMEOUT_S = 4.0

Fetcher = Callable[[str, dict[str, str]], Any]


def _http_json(url: str, headers: dict[str, str]) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - user-configured endpoint
        return json.loads(resp.read().decode("utf-8"))


def _ollama_models(payload: Any) -> list[dict[str, Any]]:
    out = []
    for m in (payload or {}).get("models", []):
        name = m.get("name") or m.get("model")
        if not name:
            continue
        details = m.get("details") or {}
        out.append({
            "id": name,
            "size": m.get("size"),
            "family": details.get("family"),
            "parameters": details.get("parameter_size"),
        })
    return out


def _openai_models(payload: Any) -> list[dict[str, Any]]:
    data = (payload or {}).get("data", [])
    return [{"id": m["id"]} for m in data if isinstance(m, dict) and m.get("id")]


def list_models(
    provider: str,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    fetch: Fetcher = _http_json,
) -> dict[str, Any]:
    """Return ``{"ok", "provider", "endpoint", "models": [{"id", ...}], "error"}``."""
    provider = (provider or "").strip()
    try:
        if provider == "ollama":
            root = (base_url or ollama_local_base()).rstrip("/")
            if root.endswith("/v1"):
                root = root[:-3]
            endpoint = f"{root}/api/tags"
            models = _ollama_models(fetch(endpoint, {}))
        elif provider == "ollama_cloud":
            key = api_key or os.environ.get("OLLAMA_API_KEY")
            if not key:
                return _fail(provider, OLLAMA_CLOUD_ROOT, "Add your Ollama API key (ollama.com/settings/keys).")
            endpoint = f"{OLLAMA_CLOUD_ROOT}/api/tags"
            models = _ollama_models(fetch(endpoint, {"Authorization": f"Bearer {key}"}))
        else:
            root, key = _openai_compat_target(provider, base_url, api_key)
            if not root:
                return _fail(provider, "", f"Model listing isn't available for '{provider}'.")
            endpoint = f"{root.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            models = _openai_models(fetch(endpoint, headers))
    except urllib.error.HTTPError as e:
        hint = " Check the API key." if e.code in (401, 403) else ""
        return _fail(provider, locals().get("endpoint", ""), f"HTTP {e.code}.{hint}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        msg = f"Couldn't reach the server ({reason})."
        if provider == "ollama":
            msg = "Ollama isn't running. Start it with `ollama serve`, or set OLLAMA_HOST."
        return _fail(provider, locals().get("endpoint", ""), msg)
    except (ValueError, KeyError, TypeError) as e:
        return _fail(provider, locals().get("endpoint", ""), f"Unexpected response: {e}")

    models.sort(key=lambda m: m["id"])
    return {"ok": True, "provider": provider, "endpoint": endpoint, "models": models, "error": None}


def _openai_compat_target(provider: str, base_url: Optional[str], api_key: Optional[str]):
    if provider == "openai":
        return base_url or "https://api.openai.com/v1", api_key or os.environ.get("OPENAI_API_KEY")
    if provider in OPENAI_COMPAT_ALIASES:
        default_base, _model, key_env = OPENAI_COMPAT_ALIASES[provider]
        return base_url or default_base, api_key or os.environ.get(key_env) or os.environ.get("NOVEL_OS_API_KEY")
    if provider == "openai_compatible":
        return base_url or os.environ.get("NOVEL_OS_BASE_URL"), api_key or os.environ.get("NOVEL_OS_API_KEY")
    return None, None


def _fail(provider: str, endpoint: str, error: str) -> dict[str, Any]:
    return {"ok": False, "provider": provider, "endpoint": endpoint, "models": [], "error": error}
