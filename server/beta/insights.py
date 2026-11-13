"""Insights over a beta round: drop-off, heat strip, confusion, reading time.

All pure functions over rows so the math is easy to test.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Optional

BUCKETS = 10
FINISHED_AT = 95  # percent at which a chapter counts as finished
REACTIONS = ("none", "love", "confused", "bored", "hooked")


def bucket(offset: Optional[int], length: int) -> int:
    """0..9: which tenth of the chapter an offset falls in."""
    if offset is None or length <= 0:
        return 0
    return max(0, min(BUCKETS - 1, int(offset * BUCKETS / length)))


def comment_offset(c, text: str) -> Optional[int]:
    if c.from_offset is not None:
        return c.from_offset
    if c.quote:
        i = text.find(c.quote)
        return i if i >= 0 else None
    return None


def dropoff(chapters: list[int], progress: Iterable) -> list[dict]:
    started: dict[int, set] = defaultdict(set)
    finished: dict[int, set] = defaultdict(set)
    for p in progress:
        if p.percent > 0:
            started[p.chapter].add(p.reader_id)
        if p.percent >= FINISHED_AT:
            finished[p.chapter].add(p.reader_id)
    return [{"chapter": n, "started": len(started[n]), "finished": len(finished[n])} for n in chapters]


def heat(chapters: list[int], texts: dict[int, str], comments: Iterable) -> list[dict]:
    rows = {n: {"chapter": n, "comments": [0] * BUCKETS,
                "reactions": {r: [0] * BUCKETS for r in REACTIONS if r != "none"}} for n in chapters}
    for c in comments:
        row = rows.get(c.chapter)
        if row is None:
            continue
        text = texts.get(c.chapter, "")
        b = bucket(comment_offset(c, text), len(text))
        if c.body.strip():
            row["comments"][b] += 1
        if c.reaction in row["reactions"]:
            row["reactions"][c.reaction][b] += 1
    for row in rows.values():
        row["total"] = [row["comments"][i] + sum(v[i] for v in row["reactions"].values()) for i in range(BUCKETS)]
    return [rows[n] for n in chapters]


def confused(comments: Iterable, limit: int = 8) -> list[dict]:
    counts: Counter = Counter()
    chapter_of: dict[tuple, int] = {}
    for c in comments:
        if c.reaction == "confused" and c.quote.strip():
            key = (c.chapter, c.quote.strip())
            counts[key] += 1
            chapter_of[key] = c.chapter
    return [{"chapter": ch, "quote": q, "count": n} for (ch, q), n in counts.most_common(limit)]


def reading_time(chapters: list[int], progress: Iterable) -> list[dict]:
    tot: dict[int, int] = defaultdict(int)
    cnt: dict[int, int] = defaultdict(int)
    for p in progress:
        if p.seconds_read > 0:
            tot[p.chapter] += p.seconds_read
            cnt[p.chapter] += 1
    return [{"chapter": n, "avg_seconds": round(tot[n] / cnt[n]) if cnt[n] else 0, "readers": cnt[n]}
            for n in chapters]
