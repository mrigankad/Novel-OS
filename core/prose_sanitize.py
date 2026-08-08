"""Sanitize agent manuscript output for human reading and house style.

- Forbid em dashes (—) in generated prose.
- Lift HTML <!-- CHAPTER … --> headers into structured metadata.
- Strip agent state-update blocks from the readable body.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Em dash and common lookalikes that models emit instead of commas/hyphens.
_EM_DASH_RE = re.compile(r"[\u2014\u2015\u2E3A\u2E3B]")  # ― ⸺ ⸻
_EN_DASH_AS_PAUSE_RE = re.compile(r"[ \t]+\u2013[ \t]+")  # spaced en-dash used as pause

# A markdown thematic break (scene break). Structure, not prose: it must survive
# the em-dash pass untouched. Collapsing "---" into " - " welds two scenes into
# one paragraph and silently destroys the author's break.
_RULE_LINE_RE = re.compile(
    r"^[ \t]*(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$"
)

_HTML_COMMENT_RE = re.compile(r"<!--([\s\S]*?)-->", re.MULTILINE)

_STATE_BLOCK_RE = re.compile(
    r"\[(?P<tag>"
    r"SCRIBE_STATE_UPDATE|EDITOR_ANALYSIS|EDITOR_STATE_UPDATE|"
    r"CONTINUITY_REPORT|CONTINUITY_STATE_UPDATE|"
    r"STYLE_ANALYSIS|STYLE_STATE_UPDATE"
    r")\][\s\S]*?(?:\[/(?P=tag)\]|(?=\[(?:SCRIBE_STATE_UPDATE|EDITOR_ANALYSIS|"
    r"EDITOR_STATE_UPDATE|CONTINUITY_REPORT|CONTINUITY_STATE_UPDATE|"
    r"STYLE_ANALYSIS|STYLE_STATE_UPDATE)\])|\Z)",
    re.IGNORECASE,
)

_CHAPTER_LINE_RE = re.compile(
    r"^CHAPTER:\s*(?P<num>\d+)\s*[-–—:]\s*(?P<title>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_FIELD_RE = re.compile(
    r"^(POV|LOCATION|TIME|WORD[_\s]?COUNT)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_em_dashes(text: str) -> str:
    """Replace em dashes with a spaced hyphen (house style: no em dash).

    Operates line by line so a dash can never swallow the newlines around it,
    and skips thematic-break lines so scene breaks survive intact.
    """
    if not text:
        return text
    return "\n".join(
        line if _RULE_LINE_RE.match(line) else _strip_em_dashes_in_line(line)
        for line in text.split("\n")
    )


def _strip_em_dashes_in_line(line: str) -> str:
    """Em-dash pass for a single line. Never crosses a newline."""
    # Preserve leading whitespace: it carries list nesting and code indentation.
    lead = len(line) - len(line.lstrip(" \t"))
    prefix, body = line[:lead], line[lead:]
    # Spaced or bare em dash (and lookalikes) becomes a spaced hyphen pause.
    body = re.sub(r"[ \t]*[—―⸺⸻][ \t]*", " - ", body)
    body = _EN_DASH_AS_PAUSE_RE.sub(" - ", body)
    # Collapse accidental " - - " artifacts left by the pass above.
    body = re.sub(r"(?:[ \t]*-[ \t]*){2,}", " - ", body)
    body = re.sub(r" {2,}", " ", body)
    return prefix + body


def repair_spaced_hyphen_corruption(text: str) -> str:
    """Undo the bug that replaced every space with ' - '.

    Safe for normal prose: only rewrites when spaced-hyphen density is extreme
    (roughly every other token), which never happens with intentional pauses.
    """
    if not text or " - " not in text:
        return text
    hits = text.count(" - ")
    if hits < 6:
        return text
    tokens = [t for t in text.split() if t != "-"]
    if not tokens:
        return text
    # Corrupted: "She - went - back" → hits ≈ len(tokens) - 1
    if hits >= max(6, int(len(tokens) * 0.4)):
        return text.replace(" - ", " ")
    return text


def parse_chapter_header(comment_body: str) -> Dict[str, Any]:
    """Parse fields from inside an HTML chapter comment."""
    meta: Dict[str, Any] = {}
    m = _CHAPTER_LINE_RE.search(comment_body)
    if m:
        meta["number"] = int(m.group("num"))
        meta["title"] = m.group("title").strip()
    for fm in _FIELD_RE.finditer(comment_body):
        key = fm.group(1).upper().replace(" ", "_")
        val = fm.group(2).strip()
        if key == "POV":
            meta["pov"] = val
        elif key == "LOCATION":
            meta["location"] = val
        elif key == "TIME":
            meta["time"] = val
        elif key.startswith("WORD"):
            # "~2550 / 2500" → keep raw; also try actual count
            meta["word_count_note"] = val
            nums = re.findall(r"\d+", val)
            if nums:
                meta["word_count"] = int(nums[0])
    return meta


def extract_html_comments(text: str) -> Tuple[str, list[Dict[str, Any]]]:
    """Remove HTML comments; return (body, list of parsed chapter metas)."""
    metas: list[Dict[str, Any]] = []

    def _repl(match: re.Match[str]) -> str:
        body = match.group(1)
        if re.search(r"CHAPTER\s*:", body, re.IGNORECASE):
            metas.append(parse_chapter_header(body))
        return ""

    cleaned = _HTML_COMMENT_RE.sub(_repl, text or "")
    return cleaned, metas


def strip_state_blocks(text: str) -> str:
    """Remove [SCRIBE_STATE_UPDATE] / editor / continuity / style blocks."""
    return _STATE_BLOCK_RE.sub("", text or "")


def sanitize_manuscript(text: str) -> Tuple[str, Dict[str, Any]]:
    """Full pipeline for agent manuscript output → clean prose + header meta.

    Returns (clean_prose, merged_header_metadata).
    """
    body, metas = extract_html_comments(text or "")
    body = strip_state_blocks(body)
    # Heal files mangled by the old every-space→" - " bug before other passes.
    body = repair_spaced_hyphen_corruption(body)
    body = strip_em_dashes(body)
    # Trim leading blank lines left by stripped header
    body = re.sub(r"^\s*\n", "", body)
    body = body.strip() + ("\n" if body.strip() else "")
    merged: Dict[str, Any] = {}
    for m in metas:
        merged.update(m)
    return body, merged


def apply_header_to_chapter(chapter: Any, meta: Dict[str, Any]) -> None:
    """Copy parsed header fields onto a ChapterState-like object."""
    if not meta or chapter is None:
        return
    if meta.get("title"):
        chapter.title = meta["title"]
    if meta.get("pov"):
        chapter.pov_character = meta["pov"]
    if meta.get("location"):
        chapter.location = meta["location"]
    if meta.get("time"):
        chapter.time = meta["time"]
    if meta.get("word_count"):
        chapter.word_count = int(meta["word_count"])
