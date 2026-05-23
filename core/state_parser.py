"""
Novel OS - Agent Output Parser

Parses the structured update blocks that agents emit (per AGENTS.md) and
applies their contents to StoryState. This is what makes the "persistent
memory" claim true: without it, agent output is discarded after rendering.

Block tags recognized:
  [SCRIBE_STATE_UPDATE] ... [/SCRIBE_STATE_UPDATE]
  [EDITOR_ANALYSIS] / [EDITOR_STATE_UPDATE]
  [CONTINUITY_REPORT] / [CONTINUITY_STATE_UPDATE]
  [STYLE_ANALYSIS] / [STYLE_STATE_UPDATE]

Field syntax supported (both forms):
  Field: value
  Field:
    - item one
    - item two

Closing tag is optional — we accept either [/TAG] or "stop at next [TAG]".
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import StoryState


# ---------------------------------------------------------------- block extract

_KNOWN_TAGS = {
    "SCRIBE_STATE_UPDATE",
    "EDITOR_ANALYSIS",
    "EDITOR_STATE_UPDATE",
    "CONTINUITY_REPORT",
    "CONTINUITY_STATE_UPDATE",
    "STYLE_ANALYSIS",
    "STYLE_STATE_UPDATE",
}


def extract_block(text: str, tag: str) -> Optional[str]:
    """Return the inner text of [TAG]...[/TAG], or [TAG]... up to next known tag."""
    open_pat = re.compile(rf"\[{re.escape(tag)}\]", re.IGNORECASE)
    close_pat = re.compile(rf"\[/{re.escape(tag)}\]", re.IGNORECASE)

    open_m = open_pat.search(text)
    if not open_m:
        return None
    start = open_m.end()
    close_m = close_pat.search(text, start)
    if close_m:
        return text[start:close_m.start()].strip()

    # No closing tag — stop at the next [KNOWN_TAG] occurrence
    rest = text[start:]
    next_tag = re.search(r"\[/?[A-Z_]+\]", rest)
    if next_tag and next_tag.group(0)[1:-1].lstrip("/").upper() in _KNOWN_TAGS:
        return rest[:next_tag.start()].strip()
    return rest.strip()


# ---------------------------------------------------------------- field parser

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_ ]*?)\s*:\s*(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*•]\s+(.+)$")


def parse_fields(block: str) -> Dict[str, Any]:
    """Parse a block of 'Field: value' / 'Field:\\n  - item' lines into a dict.

    Field keys are normalized to lower_snake_case.
    Values are str, or List[str] for bulleted/multi-line fields.
    """
    out: Dict[str, Any] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if not line.strip():
            continue
        m = _FIELD_RE.match(line.lstrip())
        if not m:
            continue
        key = _normalize_key(m.group(1))
        rest = m.group(2).strip()

        # Collect any following indented bullets as a list
        bullets: List[str] = []
        while i < len(lines):
            peek = lines[i]
            bm = _BULLET_RE.match(peek)
            if bm:
                bullets.append(bm.group(1).strip())
                i += 1
                continue
            if peek.strip() == "" and i + 1 < len(lines) and _BULLET_RE.match(lines[i + 1]):
                i += 1
                continue
            break

        if bullets:
            # If 'rest' was empty, bullets ARE the value; otherwise prepend rest.
            out[key] = bullets if not rest else [rest] + bullets
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            if not inner or inner.lower() in ("list", "count", "none"):
                out[key] = []
            else:
                out[key] = [s.strip() for s in inner.split(",") if s.strip()]
        else:
            out[key] = rest
    return out


def _normalize_key(raw: str) -> str:
    return re.sub(r"\s+", "_", raw.strip()).lower()


# ---------------------------------------------------------------- per-agent

def parse_scribe(text: str) -> Dict[str, Any]:
    block = extract_block(text, "SCRIBE_STATE_UPDATE")
    return parse_fields(block) if block else {}


def parse_editor(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for tag in ("EDITOR_ANALYSIS", "EDITOR_STATE_UPDATE"):
        block = extract_block(text, tag)
        if block:
            out.update(parse_fields(block))
    return out


def parse_continuity(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for tag in ("CONTINUITY_REPORT", "CONTINUITY_STATE_UPDATE"):
        block = extract_block(text, tag)
        if block:
            out.update(parse_fields(block))
    return out


def parse_style(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for tag in ("STYLE_ANALYSIS", "STYLE_STATE_UPDATE"):
        block = extract_block(text, tag)
        if block:
            out.update(parse_fields(block))
    return out


# ---------------------------------------------------------------- applier

def _resolve_character_id(state: "StoryState", name: str) -> Optional[str]:
    """Match a free-text character reference to an existing character id."""
    name = name.strip().strip(".,;:")
    if not name:
        return None
    if name in state.characters:
        return name
    direct = state.get_character_by_name(name)
    if direct:
        return direct.id
    # Loose match: first/last name token
    lower = name.lower()
    for char in state.characters.values():
        full = char.full_name.lower()
        if lower == full or lower in full.split():
            return char.id
    return None


def _split_pair(item: str, sep_chars: str = ":-—") -> Tuple[str, str]:
    for sep in sep_chars:
        if sep in item:
            left, _, right = item.partition(sep)
            return left.strip(), right.strip()
    return item.strip(), ""


_PLACEHOLDER = {"none", "n/a", "0", "[none]", "[n/a]", "[]", "(none)", "-"}

def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip().lower() not in _PLACEHOLDER]
    s = str(value).strip()
    if not s or s.lower() in _PLACEHOLDER:
        return []
    return [s]


def apply_to_state(
    state: "StoryState",
    chapter_number: int,
    parsed: Dict[str, Any],
    source: str,
) -> List[str]:
    """Mutate StoryState from a parsed agent block. Returns a change log."""
    log: List[str] = []
    chapter = state.get_chapter(chapter_number) or state.create_chapter(chapter_number)

    # ----- characters present -> bump last_appearance_chapter
    for raw in _as_list(parsed.get("characters_present")):
        cid = _resolve_character_id(state, raw)
        if cid:
            state.characters[cid].last_appearance_chapter = chapter_number
            log.append(f"[{source}] {state.characters[cid].full_name}: appeared in ch{chapter_number}")
        else:
            log.append(f"[{source}] unknown character referenced: {raw!r}")

    # ----- emotional shifts: "Name: new state"
    for item in _as_list(parsed.get("emotional_shifts")):
        name, new_state = _split_pair(item)
        cid = _resolve_character_id(state, name)
        if cid and new_state:
            state.characters[cid].emotional_state = new_state
            log.append(f"[{source}] {state.characters[cid].full_name}: emotional_state -> {new_state!r}")

    # ----- updated character positions (continuity guardian)
    for item in _as_list(parsed.get("updated_character_positions")):
        name, location = _split_pair(item)
        cid = _resolve_character_id(state, name)
        if cid and location:
            state.update_character_location(cid, location, chapter_number)
            log.append(f"[{source}] {state.characters[cid].full_name}: location -> {location!r}")

    # ----- key events -> timeline + chapter notes
    for ev in _as_list(parsed.get("key_events")):
        chapter.plot_advances.append(ev)
        log.append(f"[{source}] ch{chapter_number} event logged: {ev[:60]}")

    # ----- foreshadowing
    for fs in _as_list(parsed.get("foreshadowing_planted")):
        chapter.foreshadowing_planted.append(fs)
        log.append(f"[{source}] foreshadowing planted: {fs[:60]}")
    for fs in _as_list(parsed.get("foreshadowing_resolved")):
        chapter.foreshadowing_resolved.append(fs)
        log.append(f"[{source}] foreshadowing resolved: {fs[:60]}")

    # ----- new information / facts
    new_facts = _as_list(parsed.get("new_information_revealed")) + _as_list(parsed.get("new_facts_established"))
    for fact in new_facts:
        chapter.new_information.append(fact)
        log.append(f"[{source}] new fact: {fact[:60]}")

    # ----- editor quality scores
    for key in ("quality_score_before", "quality_score_after"):
        if key in parsed:
            m = re.search(r"(\d+(?:\.\d+)?)", str(parsed[key]))
            if m:
                chapter.quality_scores[key] = float(m.group(1))
                log.append(f"[{source}] {key} = {m.group(1)}")

    # ----- continuity status & issues
    if "status" in parsed:
        status = str(parsed["status"]).upper().strip()
        chapter.continuity_checks["status"] = status
        chapter.continuity_checks["validated_at"] = datetime.now().isoformat()
        log.append(f"[{source}] continuity status: {status}")
    for severity in ("critical_issues", "warnings"):
        items = _as_list(parsed.get(severity))
        if items:
            chapter.continuity_checks[severity] = items
            log.append(f"[{source}] {severity}: {len(items)}")

    # ----- style scores
    for key in ("consistency_score", "genre_adherence", "voice_strength"):
        if key in parsed:
            m = re.search(r"(\d+(?:\.\d+)?)", str(parsed[key]))
            if m:
                chapter.quality_scores[f"style_{key}"] = float(m.group(1))
                log.append(f"[{source}] style {key} = {m.group(1)}")

    chapter.last_modified = datetime.now().isoformat()
    return log


# ---------------------------------------------------------------- top-level

_DISPATCH = {
    "scribe": parse_scribe,
    "editor": parse_editor,
    "continuity_guardian": parse_continuity,
    "style_curator": parse_style,
}


def ingest_agent_output(
    state: "StoryState",
    chapter_number: int,
    agent_name: str,
    agent_output: str,
) -> List[str]:
    """One-call entry point. Parses + applies + returns change log (may be empty)."""
    parser = _DISPATCH.get(agent_name)
    if not parser:
        return []
    parsed = parser(agent_output)
    if not parsed:
        return []
    return apply_to_state(state, chapter_number, parsed, source=agent_name)
