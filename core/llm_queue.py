"""Global queue limiting concurrent LLM API calls."""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, List, NotRequired, TypedDict


class QueueFlushedError(RuntimeError):
    """Raised when a caller was queued or active and the queue was flushed."""


class QueueCancelledError(RuntimeError):
    """Raised when a queued caller was removed before acquiring a slot."""


class QueueEntry(TypedDict):
    id: str
    label: str
    submitted_at: str
    state: str  # queued | active
    chapter: NotRequired[int | None]
    project_id: NotRequired[str | None]
    function: NotRequired[str | None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LLMRequestQueue:
    """FIFO wait queue with a configurable concurrency cap."""

    def __init__(self, max_concurrent: int = 2) -> None:
        self._max = max(1, max_concurrent)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._active = 0
        self._waiting = 0
        self._flushed = False
        self._flush_reason = "Queue flushed"
        self._entries: List[QueueEntry] = []

    @property
    def max_concurrent(self) -> int:
        with self._cond:
            return self._max

    def set_max_concurrent(self, max_concurrent: int) -> None:
        with self._cond:
            self._max = max(1, max_concurrent)
            self._cond.notify_all()

    def _remove_entry(self, entry_id: str) -> None:
        self._entries = [e for e in self._entries if e["id"] != entry_id]

    def _entry_present(self, entry_id: str) -> bool:
        return any(e["id"] == entry_id for e in self._entries)

    def _public_entry(self, entry: QueueEntry) -> dict:
        out: dict = {
            "id": entry["id"],
            "label": entry["label"],
            "submitted_at": entry["submitted_at"],
        }
        if entry.get("chapter") is not None:
            out["chapter"] = entry["chapter"]
        if entry.get("project_id"):
            out["project_id"] = entry["project_id"]
        if entry.get("function"):
            out["function"] = entry["function"]
        return out

    def _status_unlocked(self) -> dict:
        active_items = [
            self._public_entry(e) for e in self._entries if e["state"] == "active"
        ]
        queued_items = [
            self._public_entry(e) for e in self._entries if e["state"] == "queued"
        ]
        return {
            "max_concurrent": self._max,
            "active": self._active,
            "queued": self._waiting,
            "flushed": self._flushed,
            "active_items": active_items,
            "queued_items": queued_items,
        }

    def status(self) -> dict:
        with self._cond:
            return self._status_unlocked()

    def flush(self, reason: str = "Queue flushed") -> dict:
        """Drop queued waiters and block new acquires. Active HTTP calls stop on process restart."""
        with self._cond:
            self._flushed = True
            self._flush_reason = reason
            self._entries = [e for e in self._entries if e["state"] == "active"]
            self._cond.notify_all()
            return self._status_unlocked()

    def _reorder_queued_unlocked(self, ordered_ids: list[str]) -> None:
        queued = [e for e in self._entries if e["state"] == "queued"]
        active = [e for e in self._entries if e["state"] == "active"]
        queued_ids = {e["id"] for e in queued}
        if set(ordered_ids) != queued_ids:
            raise ValueError("ordered_ids must match all queued entries")
        by_id = {e["id"]: e for e in queued}
        self._entries = active + [by_id[i] for i in ordered_ids]

    def reorder_queued(self, ordered_ids: list[str]) -> dict:
        with self._cond:
            self._reorder_queued_unlocked(ordered_ids)
            return self._status_unlocked()

    def move_queued(self, entry_id: str, position: str) -> dict:
        with self._cond:
            queued = [e for e in self._entries if e["state"] == "queued"]
            ids = [e["id"] for e in queued]
            if entry_id not in ids:
                raise KeyError(entry_id)
            ids.remove(entry_id)
            if position == "first":
                ids.insert(0, entry_id)
            elif position == "last":
                ids.append(entry_id)
            else:
                raise ValueError("position must be 'first' or 'last'")
            self._reorder_queued_unlocked(ids)
            return self._status_unlocked()

    def cancel_queued(self, entry_id: str) -> dict:
        with self._cond:
            found = False
            for e in self._entries:
                if e["id"] == entry_id and e["state"] == "queued":
                    found = True
                    break
            if not found:
                raise KeyError(entry_id)
            self._remove_entry(entry_id)
            self._waiting = max(0, self._waiting - 1)
            self._cond.notify_all()
            return self._status_unlocked()

    @contextmanager
    def acquire(self, label: str = "") -> Iterator[None]:
        from llm_call_context import get_llm_job_meta, resolve_llm_label  # noqa: WPS433

        entry_id = uuid.uuid4().hex[:12]
        resolved = resolve_llm_label(label)
        meta = get_llm_job_meta()
        submitted_at = _now()
        chapter = meta.get("chapter")
        chapter_int = int(chapter) if chapter is not None else None
        project_id = meta.get("project_id")
        kind = meta.get("kind")

        with self._cond:
            if self._flushed:
                raise QueueFlushedError(self._flush_reason)
            entry: QueueEntry = {
                "id": entry_id,
                "label": resolved,
                "submitted_at": submitted_at,
                "state": "queued",
                "chapter": chapter_int,
                "project_id": str(project_id) if project_id else None,
                "function": str(kind) if kind else None,
            }
            self._entries.append(entry)
            self._waiting += 1
            try:
                while self._active >= self._max:
                    if self._flushed:
                        raise QueueFlushedError(self._flush_reason)
                    if not self._entry_present(entry_id):
                        raise QueueCancelledError("Removed from queue")
                    self._cond.wait()
                if self._flushed:
                    raise QueueFlushedError(self._flush_reason)
                if not self._entry_present(entry_id):
                    raise QueueCancelledError("Removed from queue")
                self._waiting -= 1
                entry["state"] = "active"
                self._active += 1
            except (QueueFlushedError, QueueCancelledError):
                self._remove_entry(entry_id)
                self._waiting = max(0, self._waiting - 1)
                raise

        try:
            yield
        finally:
            with self._cond:
                self._remove_entry(entry_id)
                self._active = max(0, self._active - 1)
                self._cond.notify()


_queue: LLMRequestQueue | None = None
_queue_guard = threading.Lock()


def get_llm_queue() -> LLMRequestQueue:
    global _queue
    with _queue_guard:
        if _queue is None:
            from app_settings import read_max_concurrent_llm  # noqa: WPS433

            _queue = LLMRequestQueue(read_max_concurrent_llm())
        return _queue


def configure_llm_queue(max_concurrent: int) -> LLMRequestQueue:
    global _queue
    with _queue_guard:
        if _queue is None:
            _queue = LLMRequestQueue(max_concurrent)
        else:
            _queue.set_max_concurrent(max_concurrent)
        return _queue


def flush_llm_queue(reason: str = "Queue flushed") -> dict:
    return get_llm_queue().flush(reason)
