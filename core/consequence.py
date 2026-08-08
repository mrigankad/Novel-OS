"""Consequence preview helpers (PLAN.md P3.1).

Deterministic ripple = new continuity findings after a dry-applied state delta.
Anything the model invents outside the engine is labeled *predicted*.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


_REWRITTEN_RE = re.compile(
    r"\[REWRITTEN\](.*?)\[/REWRITTEN\]",
    re.DOTALL | re.IGNORECASE,
)
_PREDICTED_RE = re.compile(
    r"\[PREDICTED_CONSEQUENCES\](.*?)\[/PREDICTED_CONSEQUENCES\]",
    re.DOTALL | re.IGNORECASE,
)
_STATE_BLOCK_RE = re.compile(
    r"\[SCRIBE_STATE_UPDATE\].*?\[/SCRIBE_STATE_UPDATE\]",
    re.DOTALL | re.IGNORECASE,
)


def finding_key(f: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        f.get("category"),
        f.get("message"),
        f.get("chapter"),
        f.get("entity_id"),
    )


def diff_findings(
    before: List[Dict[str, Any]],
    after: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return findings present after dry-apply that were not present before."""
    prior = {finding_key(f) for f in before}
    out: List[Dict[str, Any]] = []
    for f in after:
        if finding_key(f) not in prior:
            out.append(dict(f))
    return out


def extract_rewritten(raw: str) -> str:
    """Prefer [REWRITTEN]…[/REWRITTEN]; else strip state blocks and return prose."""
    m = _REWRITTEN_RE.search(raw or "")
    if m:
        return m.group(1).strip()
    body = _STATE_BLOCK_RE.sub("", raw or "")
    body = _PREDICTED_RE.sub("", body)
    return body.strip()


def extract_predicted(raw: str) -> List[str]:
    m = _PREDICTED_RE.search(raw or "")
    if not m:
        return []
    lines: List[str] = []
    for line in m.group(1).splitlines():
        s = line.strip().lstrip("-•*").strip()
        if s and s.lower() not in {"none", "n/a", "(none)"}:
            lines.append(s)
    return lines


def splice_markdown(full: str, selection: str, rewritten: str) -> str:
    """Replace the first exact occurrence of selection in full with rewritten."""
    if not selection:
        raise ValueError("Selection is empty.")
    if selection not in full:
        raise ValueError("Selection not found in manuscript.")
    return full.replace(selection, rewritten, 1)
