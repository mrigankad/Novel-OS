"""Thread-local label for LLM queue entries (set by background job runner)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

_llm_job_label: ContextVar[Optional[str]] = ContextVar("llm_job_label", default=None)
_llm_job_meta: ContextVar[Optional[Dict[str, Any]]] = ContextVar("llm_job_meta", default=None)

_JOB_KIND_LABELS: Dict[str, str] = {
    "write": "Generate draft",
    "edit": "Revise",
    "validate": "Validate",
    "plan_outline": "Plan outline",
    "plan_chapter": "Plan chapter",
    "import": "Import story",
    "character_generate": "Generate character",
    "plot_generate": "Generate plot description",
    "bible_dedup_ai": "Deduplicate bible",
    "dedup_ai": "Resolve duplicates",
    "extract_background": "Extract background",
    "extract": "Extract chapter",
    "mine_characters": "Mine characters",
    "mine_plots": "Mine plot threads",
    "mine_bible": "Mine story bible",
    "regenerate": "Regenerate chapter",
    "expand_placeholders": "Expand placeholders",
    "generate_outline": "Generate outline",
}

_SCREEN_BY_KIND: Dict[str, str] = {
    "write": "Chapter",
    "edit": "Chapter",
    "validate": "Chapter",
    "extract": "Chapter",
    "regenerate": "Chapter",
    "expand_placeholders": "Chapter",
    "generate_outline": "Chapter",
    "mine_characters": "Chapter",
    "mine_plots": "Chapter",
    "mine_bible": "Chapter",
    "plan_outline": "Dashboard",
    "plan_chapter": "Dashboard",
    "import": "Dashboard",
    "character_generate": "Cast",
    "plot_generate": "Plots",
    "dedup_ai": "Plots",
    "bible_dedup_ai": "Story Bible",
    "extract_background": "Story Bible",
}


def format_timestamp(iso: Optional[str] = None) -> str:
    """Compact timestamp for queue labels (local-agnostic UTC string)."""
    if iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def screen_for_kind(kind: str, meta: Optional[Dict[str, Any]] = None) -> str:
    meta = meta or {}
    screen = meta.get("screen")
    if isinstance(screen, str) and screen.strip():
        return screen.strip()
    return _SCREEN_BY_KIND.get(kind, "App")


def format_llm_job_label(
    kind: str,
    meta: Optional[Dict[str, Any]] = None,
    *,
    started_at: Optional[str] = None,
) -> str:
    """Label: Screen · project · Ch.N · function · YYYY-MM-DD HH:MM"""
    meta = meta or {}
    screen = screen_for_kind(kind, meta)
    project = str(meta.get("project_id") or "—")
    func = _JOB_KIND_LABELS.get(kind, kind.replace("_", " ").strip().title() or "Job")
    parts = [screen, project]
    chapter = meta.get("chapter")
    if chapter is not None:
        parts.append(f"Ch.{chapter}")
    parts.append(func)
    parts.append(format_timestamp(started_at))
    return " · ".join(parts)


def get_llm_job_label() -> Optional[str]:
    return _llm_job_label.get()


def get_llm_job_meta() -> Dict[str, Any]:
    return dict(_llm_job_meta.get() or {})


def resolve_llm_label(explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    ctx = _llm_job_label.get()
    if ctx:
        return ctx
    return f"App · LLM request · {format_timestamp()}"


@contextmanager
def llm_job_context(label: str, meta: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    token = _llm_job_label.set(label)
    token_meta = _llm_job_meta.set(dict(meta or {}))
    try:
        yield
    finally:
        _llm_job_label.reset(token)
        _llm_job_meta.reset(token_meta)
