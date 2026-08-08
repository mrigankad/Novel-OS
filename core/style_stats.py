"""Deterministic manuscript statistics (PLAN.md P4 Style Curator surface).

No LLM. Word frequency, reading time, and simple echo detection so authors
can spot repeated diction without waiting on an agent.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")

# High-frequency function words — exclude from "top content words" and echoes.
_STOP = frozenset("""
a an the and or but if as at by for from in into of on to with without
is are was were be been being am do does did have has had will would
can could should may might must shall
i you he she it we they me him her us them my your his its our their
this that these those there here what which who whom whose when where why how
not no nor so than then too very just also only even still yet
said says say
""".split())

_WPM = 250  # adult fiction reading pace


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def content_tokens(tokens: Iterable[str]) -> list[str]:
    return [t for t in tokens if t not in _STOP and len(t) > 2]


def reading_minutes(word_count: int, *, wpm: int = _WPM) -> int:
    if word_count <= 0:
        return 0
    return max(1, round(word_count / max(1, wpm)))


def avg_sentence_length(text: str) -> float:
    chunks = [s.strip() for s in _SENTENCE_RE.findall(text or "") if s.strip()]
    if not chunks:
        return 0.0
    lengths = [len(tokenize(s)) for s in chunks]
    lengths = [n for n in lengths if n > 0]
    if not lengths:
        return 0.0
    return round(sum(lengths) / len(lengths), 1)


def top_words(tokens: list[str], *, limit: int = 20) -> list[dict]:
    counts = Counter(content_tokens(tokens))
    return [{"word": w, "count": n} for w, n in counts.most_common(limit)]


def find_echoes(
    tokens: list[str],
    *,
    window: int = 40,
    min_count: int = 3,
    limit: int = 15,
) -> list[dict]:
    """Flag content words that recur within `window` tokens of a prior hit.

    A word is an echo if it appears at least `min_count` times and at least
    one pair of occurrences is closer than `window` tokens.
    """
    content = content_tokens(tokens)
    if not content:
        return []

    # Map word → positions in the content stream
    positions: dict[str, list[int]] = {}
    for i, w in enumerate(content):
        positions.setdefault(w, []).append(i)

    echoes: list[dict] = []
    for word, idxs in positions.items():
        if len(idxs) < min_count:
            continue
        close = 0
        for a, b in zip(idxs, idxs[1:]):
            if b - a <= window:
                close += 1
        if close == 0:
            continue
        echoes.append({
            "word": word,
            "count": len(idxs),
            "close_pairs": close,
        })

    echoes.sort(key=lambda e: (-e["close_pairs"], -e["count"], e["word"]))
    return echoes[:limit]


def analyze_manuscript(texts: Iterable[str]) -> dict:
    """Aggregate stats across chapter manuscripts (final → revised → draft)."""
    joined = "\n\n".join(t for t in texts if (t or "").strip())
    tokens = tokenize(joined)
    wc = len(tokens)
    return {
        "word_count": wc,
        "reading_minutes": reading_minutes(wc),
        "avg_sentence_length": avg_sentence_length(joined),
        "unique_content_words": len(set(content_tokens(tokens))),
        "top_words": top_words(tokens),
        "echoes": find_echoes(tokens),
    }
