"""In-memory sliding-window rate limit, keyed by reader token."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

COMMENTS_PER_HOUR = 60
WINDOW = 3600.0

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def allow(key: str, limit: int = COMMENTS_PER_HOUR, window: float = WINDOW) -> bool:
    t = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and t - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(t)
        return True


def reset() -> None:
    with _lock:
        _hits.clear()
