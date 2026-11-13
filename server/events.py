"""In-process event bus, streamed to the browser over Server-Sent Events.

Publish from anywhere (threads included):  events.publish(project_id, "run.updated", {...})
The web app subscribes to /api/projects/{id}/events and invalidates queries.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from typing import Any, AsyncIterator

_subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def publish(project_id: str, type_: str, data: dict[str, Any] | None = None) -> None:
    """Thread-safe: callable from request handlers or worker threads."""
    payload = {"type": type_, "data": data or {}}
    with _lock:
        queues = list(_subs.get(project_id, ())) + list(_subs.get("*", ()))
    for q in queues:
        if _loop and _loop.is_running():
            _loop.call_soon_threadsafe(q.put_nowait, payload)
        else:  # pragma: no cover - tests without a loop
            q.put_nowait(payload)


async def stream(project_id: str) -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    with _lock:
        _subs[project_id].add(q)
    try:
        yield "event: ready\ndata: {}\n\n"
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=20)
                yield f"event: {item['type']}\ndata: {json.dumps(item['data'], default=str)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        with _lock:
            _subs[project_id].discard(q)
