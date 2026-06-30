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

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import PlotThread, StoryState


# ---------------------------------------------------------------- block extract

_KNOWN_TAGS = {
    "SCRIBE_STATE_UPDATE",
    "EDITOR_ANALYSIS",
    "EDITOR_STATE_UPDATE",
    "CONTINUITY_REPORT",
    "CONTINUITY_STATE_UPDATE",
    "STYLE_ANALYSIS",
    "STYLE_STATE_UPDATE",
    "IMPORT_STATE_UPDATE",
    "BACKGROUND_STATE_UPDATE",
}

# Local models (QwQ, DeepSeek-R1, etc.) often emit chain-of-thought before the real block.
_REASONING_PATTERNS = (
    r"``",
    r"``",
    r"<think>.*?</think>",
    r"<reasoning>.*?</reasoning>",
)


def _strip_model_reasoning(text: str) -> str:
    """Remove chain-of-thought wrappers some local models emit before structured blocks."""
    out = text
    for pat in _REASONING_PATTERNS:
        out = re.sub(pat, "", out, flags=re.DOTALL | re.IGNORECASE)
    return out


def parse_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object from an LLM response (thinking tags, fences, trailing prose)."""
    cleaned = _strip_model_reasoning(text).strip()
    if not cleaned:
        raise ValueError("empty response")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("no JSON object found")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = cleaned[start:i + 1]
                data = json.loads(snippet)
                if isinstance(data, dict):
                    return data
                raise ValueError("expected JSON object")
    raise ValueError("unbalanced JSON object")


def extract_block(text: str, tag: str) -> Optional[str]:
    """Return the inner text of [TAG]...[/TAG], preferring the last complete block."""
    text = _strip_model_reasoning(text)
    open_pat = re.compile(rf"\[{re.escape(tag)}\]", re.IGNORECASE)
    close_pat = re.compile(rf"\[/{re.escape(tag)}\]", re.IGNORECASE)

    opens = list(open_pat.finditer(text))
    if not opens:
        return None

    # Prefer the last [TAG]...[/TAG] pair — reasoning traces often mention the tag earlier.
    for open_m in reversed(opens):
        start = open_m.end()
        close_m = close_pat.search(text, start)
        if close_m:
            inner = text[start:close_m.start()].strip()
            if inner:
                return inner

    # No closing tag — use the last open and stop at the next known tag.
    start = opens[-1].end()
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


def parse_import(text: str) -> Dict[str, Any]:
    block = extract_block(text, "IMPORT_STATE_UPDATE")
    return parse_fields(block) if block else {}


def parse_background(text: str) -> Dict[str, Any]:
    block = extract_block(text, "BACKGROUND_STATE_UPDATE")
    return parse_fields(block) if block else {}


def parse_lorekeeper(text: str) -> Dict[str, Any]:
    return parse_background(text)


def parse_chapter_plot(text: str) -> Dict[str, Any]:
    block = extract_block(text, "CHAPTER_PLOT_UPDATE")
    return parse_fields(block) if block else {}


def parse_chapter_character(text: str) -> Dict[str, Any]:
    block = extract_block(text, "CHAPTER_CHARACTER_UPDATE")
    return parse_fields(block) if block else {}


def parse_chapter_bible(text: str) -> Dict[str, Any]:
    block = extract_block(text, "CHAPTER_BIBLE_UPDATE")
    return parse_fields(block) if block else {}


def extract_revised_chapter(text: str) -> Optional[str]:
    """Extract prose from [REVISED_CHAPTER] if present."""
    block = extract_block(text, "REVISED_CHAPTER")
    return block.strip() if block else None


def parse_archivist(text: str) -> Dict[str, Any]:
    """Merge Scribe + Import blocks from the Archivist agent."""
    out: Dict[str, Any] = {}
    out.update(parse_scribe(text))
    out.update(parse_import(text))
    return out


# ---------------------------------------------------------------- applier

def _resolve_character_id(state: "StoryState", name: str) -> Optional[str]:
    """Match a free-text character reference to an existing character id."""
    from entity_dedup import find_matching_character

    name = name.strip().strip(".,;:")
    if not name:
        return None
    if name in state.characters:
        return name
    direct = state.get_character_by_name(name)
    if direct:
        return direct.id
    fuzzy = find_matching_character(state, name, min_score=0.85)
    if fuzzy:
        return fuzzy
    return None


def _split_pair(item: str, sep_chars: str = ":-—") -> Tuple[str, str]:
    for sep in sep_chars:
        if sep in item:
            left, _, right = item.partition(sep)
            return left.strip(), right.strip()
    return item.strip(), ""


_PLACEHOLDER = {"none", "n/a", "0", "[none]", "[n/a]", "[]", "(none)", "-"}
_VALID_ROLES = frozenset({"protagonist", "antagonist", "supporting", "minor"})


def _normalize_role(role: str) -> str:
    """Map 'minor (deceased)' etc. to a valid role token."""
    r = role.strip().lower()
    for valid in _VALID_ROLES:
        if r == valid or r.startswith(valid):
            return valid
    return "supporting"

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


def _slugify_id(name: str, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return f"{prefix}_{slug}" if slug else f"{prefix}_unknown"


def _parse_pipe_fields(item: str, min_parts: int) -> Optional[List[str]]:
    parts = [p.strip() for p in item.split("|")]
    if len(parts) < min_parts:
        return None
    return parts


def apply_import_to_state(
    state: "StoryState",
    chapter_number: int,
    parsed: Dict[str, Any],
    source: str = "archivist",
) -> List[str]:
    """Apply [IMPORT_STATE_UPDATE] fields — creates characters/plot threads as needed."""
    from state_manager import Character, PlotThread  # noqa: WPS433 — runtime import avoids cycle

    log: List[str] = []
    chapter = state.get_chapter(chapter_number) or state.create_chapter(chapter_number)

    title = str(parsed.get("chapter_title", "")).strip()
    existing_title = (chapter.title or "").strip()
    if title and title.lower() not in _PLACEHOLDER:
        if existing_title:
            log.append(f"[{source}] kept chapter title {existing_title!r}")
        else:
            chapter.title = title
            log.append(f"[{source}] chapter title -> {title!r}")

    pov = str(parsed.get("pov_character", "")).strip()
    if pov and pov.lower() not in _PLACEHOLDER:
        chapter.pov_character = pov
        log.append(f"[{source}] POV -> {pov!r}")

    loc = str(parsed.get("primary_location", "")).strip()
    if loc and loc.lower() not in _PLACEHOLDER:
        chapter.location = loc

    time_ref = str(parsed.get("time_reference", "")).strip()
    if time_ref and time_ref.lower() not in _PLACEHOLDER:
        chapter.time = time_ref

    for raw in _as_list(parsed.get("new_characters")):
        parts = _parse_pipe_fields(raw, 2)
        if not parts:
            log.append(f"[{source}] skipped malformed New_Characters line: {raw!r}")
            continue
        full_name, role = parts[0], parts[1].lower()
        desc = parts[2] if len(parts) > 2 else ""
        from entity_dedup import find_matching_character, register_name_as_alias
        existing_id = find_matching_character(state, full_name, min_score=0.85)
        existing = state.characters.get(existing_id) if existing_id else None
        if existing:
            if desc and not existing.notes:
                existing.notes = desc
            if register_name_as_alias(state, existing_id, full_name):
                log.append(f"[{source}] alias added: {full_name!r} → {existing.full_name}")
            else:
                log.append(f"[{source}] merged into existing character: {existing.full_name}")
            continue
        cid = _slugify_id(full_name, "char")
        n = 2
        while cid in state.characters:
            cid = f"{_slugify_id(full_name, 'char')}_{n}"
            n += 1
        char = Character(
            id=cid,
            full_name=full_name,
            role=role if role in _VALID_ROLES else _normalize_role(role),
            notes=desc,
            last_appearance_chapter=chapter_number,
        )
        state.add_character(char)
        log.append(f"[{source}] new character: {full_name} ({cid})")

    for item in _as_list(parsed.get("character_updates")):
        name, _, rest = item.partition(":")
        name = name.strip()
        cid = _resolve_character_id(state, name)
        if not cid:
            log.append(f"[{source}] character update for unknown: {name!r}")
            continue
        char = state.characters[cid]
        for piece in rest.split(","):
            piece = piece.strip()
            if "=" not in piece:
                continue
            field, val = piece.split("=", 1)
            field = field.strip().lower()
            val = val.strip()
            if field == "location" and val:
                state.update_character_location(cid, val, chapter_number)
            elif field == "emotional_state" and val:
                char.emotional_state = val
            elif field in ("desire", "internal_desire") and val:
                char.internal_desire = val
            elif field in ("goal", "external_goal") and val:
                char.external_goal = val
            elif field == "fear" and val:
                char.fear = val
            elif field == "notes" and val:
                char.notes = val
            elif field in ("alias", "aliases") and val:
                from entity_dedup import register_name_as_alias
                for part in re.split(r"[;|]", val):
                    part = part.strip()
                    if part and state.add_character_alias(cid, part):
                        log.append(f"[{source}] {char.full_name}: alias {part!r}")
            log.append(f"[{source}] {char.full_name}: {field} updated")

    _apply_plot_import(state, parsed, chapter_number, source, log)

    for ev in _as_list(parsed.get("plot_events")):
        chapter.plot_advances.append(ev)
        log.append(f"[{source}] plot event: {ev[:60]}")

    bible_notes = _as_list(parsed.get("story_bible_notes"))
    if bible_notes:
        section = state.story_bible.get("import_notes", [])
        if not isinstance(section, list):
            section = []
        for note in bible_notes:
            entry = {"chapter": chapter_number, "note": note}
            if entry not in section:
                section.append(entry)
        state.story_bible["import_notes"] = section
        log.append(f"[{source}] story bible notes: {len(bible_notes)}")

    world_facts = _as_list(parsed.get("world_facts"))
    if world_facts:
        rules = state.story_bible.get("world_rules", [])
        if not isinstance(rules, list):
            rules = []
        for fact in world_facts:
            entry = {"chapter": chapter_number, "fact": fact}
            if entry not in rules:
                rules.append(entry)
        state.story_bible["world_rules"] = rules
        log.append(f"[{source}] world facts: {len(world_facts)}")

    relationships = _as_list(parsed.get("relationships"))
    if relationships:
        rels = state.story_bible.get("relationships", [])
        if not isinstance(rels, list):
            rels = []
        for rel in relationships:
            entry = {"chapter": chapter_number, "relationship": rel}
            if entry not in rels:
                rels.append(entry)
        state.story_bible["relationships"] = rels

    chapter.last_modified = datetime.now().isoformat()
    return log


def _merge_bible_list(state: "StoryState", key: str, items: List[str], source: str, log: List[str]) -> None:
    if not items:
        return
    section = state.story_bible.get(key, [])
    if not isinstance(section, list):
        section = [str(section)] if section else []
    for item in items:
        if item not in section:
            section.append(item)
    state.story_bible[key] = section
    log.append(f"[{source}] story bible {key}: +{len(items)}")


def _apply_character_import(
    state: "StoryState",
    parsed: Dict[str, Any],
    chapter_number: int,
    source: str,
    log: List[str],
) -> None:
    from state_manager import Character, PlotThread  # noqa: WPS433

    for raw in _as_list(parsed.get("new_characters")):
        parts = _parse_pipe_fields(raw, 2)
        if not parts:
            log.append(f"[{source}] skipped malformed New_Characters line: {raw!r}")
            continue
        full_name, role = parts[0], parts[1].lower()
        desc = parts[2] if len(parts) > 2 else ""
        from entity_dedup import find_matching_character, register_name_as_alias
        existing_id = find_matching_character(state, full_name, min_score=0.85)
        existing = state.characters.get(existing_id) if existing_id else None
        if existing:
            if desc and not existing.notes:
                existing.notes = desc
            if register_name_as_alias(state, existing_id, full_name):
                log.append(f"[{source}] alias added: {full_name!r} → {existing.full_name}")
            else:
                log.append(f"[{source}] merged into existing character: {existing.full_name}")
            continue
        cid = _slugify_id(full_name, "char")
        n = 2
        while cid in state.characters:
            cid = f"{_slugify_id(full_name, 'char')}_{n}"
            n += 1
        char = Character(
            id=cid,
            full_name=full_name,
            role=role if role in _VALID_ROLES else _normalize_role(role),
            notes=desc,
            last_appearance_chapter=chapter_number,
        )
        state.add_character(char)
        log.append(f"[{source}] new character: {full_name} ({cid})")

    _CHAR_FIELDS = {
        "location": lambda c, v, st, cn: st.update_character_location(c, v, cn),
        "emotional_state": lambda c, v, st, cn: setattr(st.characters[c], "emotional_state", v),
        "desire": lambda c, v, st, cn: setattr(st.characters[c], "internal_desire", v),
        "internal_desire": lambda c, v, st, cn: setattr(st.characters[c], "internal_desire", v),
        "goal": lambda c, v, st, cn: setattr(st.characters[c], "external_goal", v),
        "external_goal": lambda c, v, st, cn: setattr(st.characters[c], "external_goal", v),
        "fear": lambda c, v, st, cn: setattr(st.characters[c], "fear", v),
        "weakness": lambda c, v, st, cn: setattr(st.characters[c], "weakness", v),
        "strength": lambda c, v, st, cn: setattr(st.characters[c], "strength", v),
        "secret": lambda c, v, st, cn: setattr(st.characters[c], "secret", v),
        "notes": lambda c, v, st, cn: setattr(st.characters[c], "notes", v),
        "physical_description": lambda c, v, st, cn: setattr(st.characters[c], "physical_description", v),
        "age": lambda c, v, st, cn: setattr(st.characters[c], "age", int(v) if str(v).isdigit() else None),
    }

    for item in _as_list(parsed.get("character_updates")):
        name, _, rest = item.partition(":")
        name = name.strip()
        cid = _resolve_character_id(state, name)
        if not cid:
            log.append(f"[{source}] character update for unknown: {name!r}")
            continue
        for piece in rest.split(","):
            piece = piece.strip()
            if "=" not in piece:
                continue
            field, val = piece.split("=", 1)
            field = field.strip().lower()
            val = val.strip()
            if field in ("alias", "aliases") and val:
                for part in re.split(r"[;|]", val):
                    part = part.strip()
                    if part and state.add_character_alias(cid, part):
                        log.append(f"[{source}] {state.characters[cid].full_name}: alias {part!r}")
                continue
            if not val or field not in _CHAR_FIELDS:
                continue
            _CHAR_FIELDS[field](cid, val, state, chapter_number)
            log.append(f"[{source}] {state.characters[cid].full_name}: {field} updated")


def _append_subplot_beat(
    state: "StoryState",
    thread_name: str,
    beat: str,
    *,
    source: str,
    log: List[str],
) -> None:
    from entity_dedup import find_matching_plot_thread

    beat = beat.strip()
    if not beat:
        return
    tid = find_matching_plot_thread(state, thread_name.strip(), min_score=0.72)
    if not tid:
        log.append(f"[{source}] no plot thread for subplot beat: {thread_name!r}")
        return
    _append_subplot_line(state.plot_threads[tid], beat, source=source, log=log, label=thread_name)


def _append_subplot_line(
    thread: "PlotThread",
    line: str,
    *,
    source: str,
    log: List[str],
    label: str = "",
) -> None:
    line = line.strip()
    if not line:
        return
    seen = {s.strip().lower() for s in thread.subplots if s.strip()}
    if line.lower() not in seen:
        thread.subplots.append(line)
        who = label or thread.name
        log.append(f"[{source}] subplot on {who}: {line[:72]}")


_NON_MAIN_PLOT_TYPES = frozenset({"subplot", "character_arc", "mystery"})


def _attach_related_plot_as_subplot(
    state: "StoryState",
    *,
    name: str,
    thread_type: str,
    desc: str,
    related: List[str],
    parent_hint: str,
    chapter_number: int,
    source: str,
    log: List[str],
) -> bool:
    """Store a related plot under a major thread's subplots list. Returns True if attached."""
    from entity_dedup import (
        find_matching_plot_thread,
        find_parent_plot_thread,
        format_subplot_line,
    )

    related_ids = [
        cid for rn in related
        if (cid := _resolve_character_id(state, rn))
    ]
    parent_id = find_parent_plot_thread(
        state,
        parent_hint=parent_hint,
        subplot_name=name,
        description=desc,
        related_char_ids=related_ids,
    )
    if not parent_id:
        return False

    parent = state.plot_threads[parent_id]
    line = format_subplot_line(name, desc)
    _append_subplot_line(parent, line, source=source, log=log, label=parent.name)
    parent.last_updated_chapter = max(parent.last_updated_chapter, chapter_number)
    for cid in related_ids:
        if cid not in parent.related_characters:
            parent.related_characters.append(cid)

    # Remove a wrongly-created top-level thread with the same name.
    dup_id = find_matching_plot_thread(state, name, min_score=0.88)
    if dup_id and dup_id != parent_id:
        dup = state.plot_threads.get(dup_id)
        if dup and dup.thread_type in _NON_MAIN_PLOT_TYPES:
            state.delete_plot_thread(dup_id)
            log.append(f"[{source}] removed duplicate top-level thread {name!r}")

    log.append(
        f"[{source}] related {thread_type} {name!r} → subplot of {parent.name!r}",
    )
    return True


def _remove_resolved_subplots(
    state: "StoryState",
    parsed: Dict[str, Any],
    *,
    source: str,
    log: List[str],
) -> None:
    from entity_dedup import find_matching_plot_thread, match_subplot_index

    for raw in _as_list(parsed.get("resolved_subplots")):
        parts = _parse_pipe_fields(raw, 1)
        if not parts:
            continue
        if len(parts) >= 2:
            parent_name, sub_name = parts[0], parts[1]
            resolution = parts[2] if len(parts) > 2 else ""
            parent_id = find_matching_plot_thread(state, parent_name, min_score=0.68)
            if not parent_id:
                log.append(f"[{source}] no parent for resolved subplot: {parent_name!r}")
                continue
            thread = state.plot_threads[parent_id]
            idx = match_subplot_index(thread.subplots, sub_name)
            if idx is None:
                log.append(f"[{source}] resolved subplot not found on {parent_name!r}: {sub_name!r}")
                continue
            removed = thread.subplots.pop(idx)
            note = f" ({resolution[:50]})" if resolution else ""
            log.append(f"[{source}] resolved subplot removed from {thread.name}: {removed[:60]}{note}")
            continue

        sub_name = parts[0]
        found = False
        for thread in state.plot_threads.values():
            idx = match_subplot_index(thread.subplots, sub_name)
            if idx is None:
                continue
            removed = thread.subplots.pop(idx)
            log.append(f"[{source}] resolved subplot removed from {thread.name}: {removed[:60]}")
            found = True
            break
        if not found:
            log.append(f"[{source}] resolved subplot not found: {sub_name!r}")


def _apply_plot_import(
    state: "StoryState",
    parsed: Dict[str, Any],
    chapter_number: int,
    source: str,
    log: List[str],
) -> None:
    from state_manager import PlotThread  # noqa: WPS433
    from entity_dedup import find_matching_plot_thread

    for raw in _as_list(parsed.get("subplot_threads")):
        parts = _parse_pipe_fields(raw, 2)
        if len(parts) < 2:
            log.append(f"[{source}] skipped malformed Subplot_Threads line: {raw!r}")
            continue
        parent_name, sub_name = parts[0], parts[1]
        sub_desc = parts[2] if len(parts) > 2 else sub_name
        parent_id = find_matching_plot_thread(state, parent_name, min_score=0.68)
        if not parent_id:
            log.append(f"[{source}] no parent plot for subplot: {parent_name!r}")
            continue
        parent = state.plot_threads[parent_id]
        from entity_dedup import format_subplot_line
        line = format_subplot_line(sub_name, sub_desc)
        _append_subplot_line(parent, line, source=source, log=log, label=parent.name)
        parent.last_updated_chapter = max(parent.last_updated_chapter, chapter_number)

    for raw in _as_list(parsed.get("plot_threads")):
        parts = _parse_pipe_fields(raw, 2)
        if not parts:
            continue
        name, thread_type = parts[0], parts[1].lower()
        desc = parts[2] if len(parts) > 2 else name
        related = []
        if len(parts) > 3:
            related = [n.strip() for n in parts[3].split(",") if n.strip()]
        parent_hint = parts[4].strip() if len(parts) > 4 else ""

        if thread_type in _NON_MAIN_PLOT_TYPES:
            if _attach_related_plot_as_subplot(
                state,
                name=name,
                thread_type=thread_type,
                desc=desc,
                related=related,
                parent_hint=parent_hint,
                chapter_number=chapter_number,
                source=source,
                log=log,
            ):
                continue
            log.append(
                f"[{source}] no parent for {thread_type} {name!r} — stored as top-level thread",
            )

        existing_id = find_matching_plot_thread(state, name, min_score=0.78)
        if existing_id:
            thread = state.plot_threads[existing_id]
            if desc and (not thread.description or thread.description == thread.name):
                thread.description = desc
            thread.last_updated_chapter = max(thread.last_updated_chapter, chapter_number)
            if related:
                for rn in related:
                    cid = _resolve_character_id(state, rn)
                    if cid and cid not in thread.related_characters:
                        thread.related_characters.append(cid)
            log.append(f"[{source}] plot thread updated: {name}")
        else:
            tid = _slugify_id(name, "plot")
            n = 2
            while tid in state.plot_threads:
                tid = f"{_slugify_id(name, 'plot')}_{n}"
                n += 1
            thread = PlotThread(
                id=tid,
                name=name,
                description=desc,
                thread_type=thread_type if thread_type in ("main", "subplot", "character_arc", "mystery") else "main",
                start_chapter=chapter_number,
                last_updated_chapter=chapter_number,
                related_characters=[
                    _resolve_character_id(state, rn)
                    for rn in related
                    if _resolve_character_id(state, rn)
                ],
            )
            state.add_plot_thread(thread)
            log.append(f"[{source}] new plot thread: {name} ({tid})")

    for raw in _as_list(parsed.get("subplot_beats")):
        parts = _parse_pipe_fields(raw, 1)
        if len(parts) < 2:
            log.append(f"[{source}] skipped malformed Subplot_Beats line: {raw!r}")
            continue
        _append_subplot_beat(state, parts[0], parts[1], source=source, log=log)

    _remove_resolved_subplots(state, parsed, source=source, log=log)


def apply_chapter_plot_mine(
    state: "StoryState",
    chapter_number: int,
    parsed: Dict[str, Any],
    *,
    source: str = "mine_plots",
) -> List[str]:
    log: List[str] = []
    chapter = state.get_chapter(chapter_number) or state.create_chapter(chapter_number)
    _apply_plot_import(state, parsed, chapter_number, source, log)
    for ev in _as_list(parsed.get("plot_events")):
        chapter.plot_advances.append(ev)
        log.append(f"[{source}] plot event: {ev[:60]}")
    return log


def apply_chapter_character_mine(
    state: "StoryState",
    chapter_number: int,
    parsed: Dict[str, Any],
    *,
    source: str = "mine_characters",
) -> List[str]:
    log: List[str] = []
    apply_to_state(state, chapter_number, parsed, source=source)
    _apply_character_import(state, parsed, chapter_number, source, log)
    return log


def apply_chapter_bible_mine(
    state: "StoryState",
    chapter_number: int,
    parsed: Dict[str, Any],
    *,
    source: str = "mine_bible",
    label: str = "Chapter",
) -> List[str]:
    log: List[str] = []
    chapter = state.get_chapter(chapter_number) or state.create_chapter(chapter_number)

    bible_notes = _as_list(parsed.get("story_bible_notes"))
    if bible_notes:
        section = state.story_bible.get("import_notes", [])
        if not isinstance(section, list):
            section = []
        for note in bible_notes:
            entry = {"chapter": chapter_number, "note": note}
            if entry not in section:
                section.append(entry)
        state.story_bible["import_notes"] = section
        log.append(f"[{source}] story bible notes: {len(bible_notes)}")

    world_facts = _as_list(parsed.get("world_facts"))
    if world_facts:
        rules = state.story_bible.get("world_rules", [])
        if not isinstance(rules, list):
            rules = []
        for fact in world_facts:
            entry = {"chapter": chapter_number, "fact": fact}
            if entry not in rules:
                rules.append(entry)
        state.story_bible["world_rules"] = rules
        log.append(f"[{source}] world facts: {len(world_facts)}")

    setting = _as_list(parsed.get("setting_details"))
    if setting:
        _merge_bible_list(state, "setting_summary", setting, source, log)

    relationships = _as_list(parsed.get("relationships"))
    if relationships:
        rels = state.story_bible.get("relationships", [])
        if not isinstance(rels, list):
            rels = []
        for rel in relationships:
            entry = {"chapter": chapter_number, "relationship": rel}
            if entry not in rels:
                rels.append(entry)
        state.story_bible["relationships"] = rels
        log.append(f"[{source}] relationships: {len(relationships)}")

    return log


def apply_background_to_state(
    state: "StoryState",
    parsed: Dict[str, Any],
    *,
    source: str = "lorekeeper",
    label: str = "Background",
) -> List[str]:
    """Apply [BACKGROUND_STATE_UPDATE] at story level — characters, plot, story bible."""
    log: List[str] = []
    chapter_number = 0

    summary = str(parsed.get("block_summary", "")).strip()
    if summary and summary.lower() not in _PLACEHOLDER:
        blocks = state.story_bible.get("background_blocks", [])
        if not isinstance(blocks, list):
            blocks = []
        blocks.append({
            "label": label,
            "summary": summary,
            "extracted_at": datetime.now().isoformat(),
        })
        state.story_bible["background_blocks"] = blocks
        log.append(f"[{source}] recorded background block: {label!r}")

    logline = str(parsed.get("logline", "")).strip()
    if logline and logline.lower() not in _PLACEHOLDER:
        state.story_bible["logline"] = logline
        log.append(f"[{source}] logline updated")

    tone = str(parsed.get("tone", "")).strip()
    if tone and tone.lower() not in _PLACEHOLDER:
        state.story_bible["tone"] = tone
        log.append(f"[{source}] tone updated")

    _merge_bible_list(state, "themes", _as_list(parsed.get("themes")), source, log)
    _merge_bible_list(state, "setting_summary", _as_list(parsed.get("setting_summary")), source, log)
    _merge_bible_list(state, "historical_context", _as_list(parsed.get("historical_context")), source, log)
    _merge_bible_list(state, "premise_beats", _as_list(parsed.get("premise_beats")), source, log)

    tech = _as_list(parsed.get("technology_or_magic"))
    if tech:
        key = "magic_system" if "magic_system" in state.story_bible else "technology"
        if key not in state.story_bible:
            state.story_bible[key] = {}
        bucket = state.story_bible[key]
        if isinstance(bucket, dict):
            notes = bucket.get("notes", [])
            if not isinstance(notes, list):
                notes = []
            for t in tech:
                if t not in notes:
                    notes.append(t)
            bucket["notes"] = notes
        else:
            _merge_bible_list(state, key, tech, source, log)
        log.append(f"[{source}] {key} rules: +{len(tech)}")

    _apply_character_import(state, parsed, chapter_number, source, log)
    _apply_plot_import(state, parsed, chapter_number, source, log)

    bible_notes = _as_list(parsed.get("story_bible_notes"))
    if bible_notes:
        section = state.story_bible.get("import_notes", [])
        if not isinstance(section, list):
            section = []
        for note in bible_notes:
            entry = {"source": label, "note": note}
            if entry not in section:
                section.append(entry)
        state.story_bible["import_notes"] = section
        log.append(f"[{source}] story bible notes: {len(bible_notes)}")

    world_facts = _as_list(parsed.get("world_facts"))
    if world_facts:
        rules = state.story_bible.get("world_rules", [])
        if not isinstance(rules, list):
            rules = []
        for fact in world_facts:
            entry = {"source": label, "fact": fact}
            if entry not in rules:
                rules.append(entry)
        state.story_bible["world_rules"] = rules
        log.append(f"[{source}] world facts: {len(world_facts)}")

    relationships = _as_list(parsed.get("relationships"))
    if relationships:
        rels = state.story_bible.get("relationships", [])
        if not isinstance(rels, list):
            rels = []
        for rel in relationships:
            entry = {"source": label, "relationship": rel}
            if entry not in rels:
                rels.append(entry)
        state.story_bible["relationships"] = rels
        log.append(f"[{source}] relationships: {len(relationships)}")

    state.set_metadata("background_extracted", True)
    return log


# ---------------------------------------------------------------- top-level

_DISPATCH = {
    "scribe": parse_scribe,
    "editor": parse_editor,
    "continuity_guardian": parse_continuity,
    "style_curator": parse_style,
    "archivist": parse_archivist,
    "lorekeeper": parse_lorekeeper,
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
    if agent_name == "lorekeeper":
        return apply_background_to_state(state, parsed, source=agent_name)
    log = apply_to_state(state, chapter_number, parsed, source=agent_name)
    if agent_name == "archivist":
        log.extend(apply_import_to_state(state, chapter_number, parsed, source=agent_name))
    return log
