"""Pronunciation dictionary: whole-word, case-insensitive substitution before TTS."""

from __future__ import annotations

import re
from typing import Iterable


def apply(text: str, pairs: Iterable[tuple[str, str]]) -> str:
    """Replace each term (whole words, any case) with its say-as. Longest terms win, so
    "Iris Vale" beats "Iris"."""
    items = sorted(((t.strip(), s) for t, s in pairs if t and t.strip() and s), key=lambda p: -len(p[0]))
    if not items:
        return text
    lookup = {t.lower(): s for t, s in items}
    pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(t) for t, _ in items) + r")(?!\w)", re.IGNORECASE)
    return pattern.sub(lambda m: lookup[m.group(1).lower()], text)


COMMON = {"the", "a", "an", "of", "and", "old", "new", "north", "south", "east", "west", "mr", "mrs", "dr"}


def suggest(names: Iterable[str], existing: Iterable[str] = ()) -> list[str]:
    """Codex names worth a pronunciation: full names plus their capitalised parts."""
    have = {e.lower() for e in existing}
    out: list[str] = []
    for name in names:
        name = (name or "").strip()
        for cand in ([name, *name.split()] if " " in name else [name]):
            c = cand.strip(".,'\"")
            if len(c) < 3 or c.lower() in COMMON or c.lower() in have or not c[:1].isupper():
                continue
            have.add(c.lower())
            out.append(c)
    return out
