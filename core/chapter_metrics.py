"""Outliner chapter metrics: tension, emotional intensity, pacing (PLAN.md P4).

Deterministic Style Curator heuristics so the outliner can sort without an
LLM round-trip. Scores are 1–10 integers stored on binder `derived`.
"""

from __future__ import annotations

import re
from typing import Iterable

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")
_DIALOGUE_RE = re.compile(r'"[^"\n]{2,}"|“[^”\n]{2,}”')

_TENSION = frozenset("""
danger threat blood chase scream weapon fight fear dead death kill risk trap
escape gun knife panic wound blade enemy attack flee hide stalk hunted
betrayal ambush hostage poison explosion crash collision bloodstained
""".split())

_EMOTION = frozenset("""
love hate grief tears tear heart ache hope despair rage joy fear lonely
loneliness sorrow guilt shame pride tender tenderness weep crying cried cry
aching longing anger angry furious warmth warm cold hollow empty
heartbroken heartbreak
""".split())


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text or "") if s.strip()]


def _clamp_score(raw: float) -> int:
    return max(1, min(10, int(round(raw))))


def _density(hits: int, total: int, *, scale: float = 80.0) -> float:
    if total <= 0:
        return 1.0
    return 1.0 + min(9.0, (hits / total) * scale)


def score_chapter(
    text: str,
    *,
    synopsis: str = "",
    outline: str = "",
) -> dict:
    """Return tension / emotional_intensity / pacing scores (1–10)."""
    body = (text or "").strip() or (synopsis or "").strip() or (outline or "").strip()
    tokens = _tokens(body)
    n = len(tokens)
    sents = _sentences(body)

    # --- tension ---
    t_hits = sum(1 for t in tokens if t in _TENSION)
    excl = body.count("!") + body.count("?")
    short = sum(1 for s in sents if 0 < len(_tokens(s)) <= 8)
    short_ratio = (short / len(sents)) if sents else 0.0
    tension = _density(t_hits, n, scale=90.0)
    tension += min(2.0, excl * 0.35)
    tension += short_ratio * 2.0

    # --- emotional intensity ---
    e_hits = sum(1 for t in tokens if t in _EMOTION)
    emotion = _density(e_hits, n, scale=100.0)
    # First-person density as intimacy proxy
    fp = sum(1 for t in tokens if t in {"i", "me", "my", "mine", "we", "our"})
    emotion += min(2.0, _density(fp, n, scale=40.0) - 1.0)

    # --- pacing (higher = faster) ---
    avg_len = (sum(len(_tokens(s)) for s in sents) / len(sents)) if sents else 18.0
    # 6 words → ~9, 25 words → ~3
    pace_from_len = max(1.0, min(9.0, 12.0 - (avg_len - 6) * 0.45))
    dialogue_chars = sum(len(m.group(0)) for m in _DIALOGUE_RE.finditer(body))
    dialogue_ratio = dialogue_chars / max(1, len(body))
    pacing = pace_from_len + min(2.5, dialogue_ratio * 8.0)
    if n < 40 and not body:
        pacing = 5.0
        tension = 3.0
        emotion = 3.0
    elif n < 40:
        # Thin text: dampen extremes toward mid
        tension = (tension + 5) / 2
        emotion = (emotion + 5) / 2
        pacing = (pacing + 5) / 2

    return {
        "tension": _clamp_score(tension),
        "emotional_intensity": _clamp_score(emotion),
        "pacing": _clamp_score(pacing),
        "source": "heuristic",
        "word_count": n,
    }


def score_many(chapters: Iterable[dict]) -> list[dict]:
    """chapters: [{chapter, text, synopsis?, outline?}, …] → scored rows."""
    out = []
    for ch in chapters:
        metrics = score_chapter(
            ch.get("text") or "",
            synopsis=ch.get("synopsis") or "",
            outline=ch.get("outline") or "",
        )
        out.append({"chapter": int(ch["chapter"]), **metrics})
    return out
