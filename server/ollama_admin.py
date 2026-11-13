"""Local Ollama administration: list, pull (streamed), delete, plus a curated library.

All HTTP goes through ``_client()``; tests set ``TRANSPORT`` to an ``httpx.MockTransport``.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Iterator, Optional

import httpx

from core.llm_client import ollama_local_base

TRANSPORT: Optional[httpx.BaseTransport] = None  # injected by tests
MODEL_RE = re.compile(r"^[a-zA-Z0-9._:/-]{1,120}$")
NOT_RUNNING = "Ollama isn't running. Start Ollama, or install it from ollama.com/download."
PROGRESS_INTERVAL = 0.2  # at most ~5 progress events per second

# Suggestions only, verify on ollama.com/library. Cloud models run on ollama.com and need no pull.
LIBRARY: list[dict[str, Any]] = [
    {"name": "qwen3:32b", "label": "Qwen3 32B", "size": "20 GB", "best_for": "Drafting and long-context planning", "cloud": False},
    {"name": "qwen3:14b", "label": "Qwen3 14B", "size": "9.3 GB", "best_for": "Fast drafting on 16 GB GPUs", "cloud": False},
    {"name": "gemma3:27b", "label": "Gemma 3 27B", "size": "17 GB", "best_for": "Prose", "cloud": False},
    {"name": "gemma3:12b", "label": "Gemma 3 12B", "size": "8.1 GB", "best_for": "Prose on smaller machines", "cloud": False},
    {"name": "llama3.3:70b", "label": "Llama 3.3 70B", "size": "43 GB", "best_for": "Editing and critique", "cloud": False},
    {"name": "mistral-small3.2", "label": "Mistral Small 3.2", "size": "15 GB", "best_for": "Dialogue and voice", "cloud": False},
    {"name": "deepseek-r1:14b", "label": "DeepSeek-R1 14B", "size": "9 GB", "best_for": "Plot logic and continuity", "cloud": False},
    {"name": "nomic-embed-text", "label": "Nomic Embed Text", "size": "274 MB", "best_for": "Embeddings for memory recall", "cloud": False},
    {"name": "gpt-oss:120b-cloud", "label": "gpt-oss 120B", "size": "cloud", "best_for": "All-round writing, no download", "cloud": True},
    {"name": "qwen3-coder:480b-cloud", "label": "Qwen3 Coder 480B", "size": "cloud", "best_for": "Structured outlines", "cloud": True},
    {"name": "deepseek-v3.1:671b-cloud", "label": "DeepSeek V3.1 671B", "size": "cloud", "best_for": "Long, careful revisions", "cloud": True},
]


class OllamaError(Exception):
    pass


def valid_model(name: str) -> bool:
    return bool(MODEL_RE.match(name or "")) and ".." not in name


def resolve_base(base_url: Optional[str]) -> str:
    root = (base_url or "").strip().rstrip("/") or ollama_local_base()
    if not root.startswith(("http://", "https://")):
        root = "http://" + root
    return root[:-3] if root.endswith("/v1") else root


def _client(base: str, read_timeout: Optional[float] = 10.0) -> httpx.Client:
    timeout = httpx.Timeout(10.0, read=read_timeout, connect=3.0)
    return httpx.Client(base_url=base, timeout=timeout, transport=TRANSPORT)


def human_size(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1000:
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1000
    return f"{size:.1f} TB"


def list_installed(base_url: Optional[str]) -> dict[str, Any]:
    base = resolve_base(base_url)
    empty = {"reachable": False, "base_url": base, "version": "", "models": [], "running": []}
    try:
        with _client(base) as c:
            version = c.get("/api/version").json().get("version", "")
            tags = c.get("/api/tags").json().get("models", []) or []
            try:
                ps = c.get("/api/ps").json().get("models", []) or []
            except (httpx.HTTPError, ValueError):
                ps = []
    except httpx.TransportError:
        return {**empty, "error": NOT_RUNNING}
    except (httpx.HTTPError, ValueError, AttributeError) as e:
        return {**empty, "error": f"Ollama answered unexpectedly ({e})."}
    loaded = {m.get("name") or m.get("model") for m in ps}
    models = []
    for m in tags:
        name = m.get("name") or m.get("model") or ""
        d = m.get("details") or {}
        size = int(m.get("size") or 0)
        models.append({
            "name": name, "size": size, "size_human": human_size(size),
            "family": d.get("family", ""), "parameter_size": d.get("parameter_size", ""),
            "quantization": d.get("quantization_level", ""), "modified_at": m.get("modified_at"),
            "loaded": name in loaded,
        })
    running = [{"name": m.get("name") or m.get("model"), "size_vram": m.get("size_vram"),
                "expires_at": m.get("expires_at"), "loaded": True} for m in ps]
    return {"reachable": True, "base_url": base, "version": version, "models": models,
            "running": running, "error": None}


def delete_model(base_url: Optional[str], name: str) -> None:
    try:
        with _client(resolve_base(base_url)) as c:
            r = c.request("DELETE", "/api/delete", json={"model": name})
    except httpx.TransportError as e:
        raise OllamaError(NOT_RUNNING) from e
    if r.status_code == 404:
        raise OllamaError(f"{name} isn't installed.")
    if r.status_code >= 400:
        raise OllamaError(f"Ollama refused the delete (HTTP {r.status_code}).")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def pull_events(base_url: Optional[str], model: str) -> Iterator[str]:
    """Yield SSE strings: throttled ``progress`` events, then ``done`` or ``error``."""
    last_emit = 0.0
    last_status = None
    try:
        with _client(resolve_base(base_url), read_timeout=None) as c:
            with c.stream("POST", "/api/pull", json={"model": model, "stream": True}) as r:
                if r.status_code >= 400:
                    r.read()
                    yield _sse("error", {"error": f"Ollama refused the pull (HTTP {r.status_code}): {r.text[:200]}"})
                    return
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if msg.get("error"):
                        yield _sse("error", {"error": str(msg["error"])})
                        return
                    status = str(msg.get("status", ""))
                    total = int(msg.get("total") or 0)
                    completed = int(msg.get("completed") or 0)
                    percent = round(completed * 100 / total, 1) if total else None
                    if status == "success":
                        yield _sse("done", {"model": model, "status": "success"})
                        return
                    now = time.monotonic()
                    if status != last_status or now - last_emit >= PROGRESS_INTERVAL:
                        last_emit, last_status = now, status
                        yield _sse("progress", {"status": status, "percent": percent,
                                                "completed": completed, "total": total})
        yield _sse("error", {"error": "The pull ended before Ollama reported success."})
    except httpx.TransportError:
        yield _sse("error", {"error": NOT_RUNNING})
    except httpx.HTTPError as e:
        yield _sse("error", {"error": f"Pull failed: {e}"})
