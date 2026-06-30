"""
Detect and merge duplicate / near-duplicate story bible list entries.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import StoryState


LIST_SECTIONS = (
    "themes",
    "setting_summary",
    "historical_context",
    "premise_beats",
    "import_notes",
)

_TEXT_SECTIONS = ("world_rules", "import_notes")


@dataclass
class BibleItemRef:
    section: str
    index: int
    text: str

    @property
    def ref_id(self) -> str:
        return f"{self.section}:{self.index}"


@dataclass
class BibleDuplicateGroup:
    section: str  # primary section (all members same section for heuristic groups)
    confidence: float
    reason: str
    suggested_keep_index: int
    members: List[Dict[str, Any]] = field(default_factory=list)


def item_text(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("note", "fact", "rule", "relationship", "text"):
            val = raw.get(key)
            if val and str(val).strip():
                return str(val).strip()
        return json.dumps(raw, ensure_ascii=False)
    return str(raw).strip()


def section_items(story_bible: Dict[str, Any], section: str) -> List[str]:
    raw = story_bible.get(section)
    if raw is None:
        return []
    if isinstance(raw, list):
        return [t for t in (item_text(x) for x in raw) if t]
    if isinstance(raw, str):
        if section in _TEXT_SECTIONS and "\n" not in raw.strip() and section != "import_notes":
            return [raw.strip()] if raw.strip() else []
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return [item_text(raw)] if item_text(raw) else []


def set_section_items(story_bible: Dict[str, Any], section: str, items: List[str]) -> None:
    if section == "world_rules" and len(items) == 1 and "\n" not in items[0]:
        story_bible[section] = items[0]
    else:
        story_bible[section] = items


def normalize_text(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def bible_match_score(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 0.98
    if na in nb or nb in na:
        short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
        return 0.86 + 0.12 * (len(short) / max(len(long), 1))
    ratio = SequenceMatcher(None, na, nb).ratio()
    if ratio >= 0.82:
        return ratio
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb:
        j = len(ta & tb) / len(ta | tb)
        if j >= 0.65:
            return 0.72 + 0.25 * j
    return 0.0


def collect_bible_items(story_bible: Dict[str, Any]) -> List[BibleItemRef]:
    refs: List[BibleItemRef] = []
    sections = list(LIST_SECTIONS) + ["world_rules"]
    for section in sections:
        for idx, text in enumerate(section_items(story_bible, section)):
            refs.append(BibleItemRef(section=section, index=idx, text=text))
    return refs


def find_bible_duplicate_groups(
    story_bible: Dict[str, Any],
    *,
    min_score: float = 0.85,
    within_section_only: bool = True,
) -> List[BibleDuplicateGroup]:
    """Find groups of similar bible entries (heuristic)."""
    refs = collect_bible_items(story_bible)
    groups: List[BibleDuplicateGroup] = []
    used: set[str] = set()

    for i, a in enumerate(refs):
        if a.ref_id in used:
            continue
        cluster = [a]
        for b in refs[i + 1 :]:
            if b.ref_id in used:
                continue
            if within_section_only and a.section != b.section:
                continue
            score = bible_match_score(a.text, b.text)
            if score >= min_score:
                cluster.append(b)
        if len(cluster) < 2:
            continue
        for m in cluster:
            used.add(m.ref_id)
        # Keep the longest / most informative line
        keep = max(cluster, key=lambda r: (len(r.text), -r.index))
        members = [
            {"section": r.section, "index": r.index, "label": r.text, "id": r.ref_id}
            for r in cluster
        ]
        avg_score = 0.9
        groups.append(
            BibleDuplicateGroup(
                section=keep.section,
                confidence=avg_score,
                reason="Similar wording in story bible",
                suggested_keep_index=keep.index,
                members=members,
            )
        )
    return groups


def apply_bible_dedupe_group(
    story_bible: Dict[str, Any],
    *,
    section: str,
    keep_index: int,
    merge_indices: List[int],
) -> tuple[List[str], int]:
    """Remove duplicate indices from one bible section; keep one line. Returns (log, final keep_index)."""
    items = section_items(story_bible, section)
    if not items:
        return [], keep_index
    if keep_index < 0 or keep_index >= len(items):
        raise ValueError(f"Invalid keep_index {keep_index} for section {section!r}")
    log: List[str] = []
    remove = sorted({i for i in merge_indices if i != keep_index and 0 <= i < len(items)}, reverse=True)
    keep_text = items[keep_index]
    for idx in remove:
        removed = items.pop(idx)
        log.append(f"Removed duplicate from {section}: {removed[:60]!r}")
        if idx < keep_index:
            keep_index -= 1
    if keep_index < len(items):
        items[keep_index] = keep_text
    set_section_items(story_bible, section, items)
    return log, keep_index


def apply_bible_group_members(
    story_bible: Dict[str, Any],
    members: List[Dict[str, Any]],
    keep_section: str,
    keep_index: int,
    *,
    text_override: str = "",
) -> List[str]:
    """Remove redundant bible lines; keep one member. Optionally replace kept text."""
    log: List[str] = []
    final_keep_index = keep_index
    by_section: Dict[str, List[int]] = {}
    for m in members:
        sec = str(m.get("section", keep_section))
        idx = int(m.get("index", -1))
        if sec == keep_section and idx == keep_index:
            continue
        if idx >= 0:
            by_section.setdefault(sec, []).append(idx)

    for sec, indices in by_section.items():
        if sec == keep_section:
            sec_log, final_keep_index = apply_bible_dedupe_group(
                story_bible,
                section=sec,
                keep_index=keep_index,
                merge_indices=indices,
            )
            log.extend(sec_log)
        else:
            items = section_items(story_bible, sec)
            for idx in sorted(set(indices), reverse=True):
                if 0 <= idx < len(items):
                    removed = items.pop(idx)
                    log.append(f"Removed duplicate from {sec}: {removed[:60]!r}")
            set_section_items(story_bible, sec, items)

    override = text_override.strip()
    if override:
        items = section_items(story_bible, keep_section)
        if final_keep_index < 0 or final_keep_index >= len(items):
            raise ValueError(
                f"Cannot apply text override — keep_index {final_keep_index} invalid for {keep_section!r}",
            )
        items[final_keep_index] = override
        set_section_items(story_bible, keep_section, items)
        log.append(f"Canonical text set in {keep_section}")
    elif not log:
        raise ValueError(
            "No bible lines were removed — indices may be stale. Run Quick scan again.",
        )
    return log


def filter_stale_bible_groups(
    story_bible: Dict[str, Any],
    groups: List[Dict[str, Any]],
    *,
    min_label_score: float = 0.82,
) -> List[Dict[str, Any]]:
    """Drop AI/heuristic groups whose members no longer match live bible indices."""
    out: List[Dict[str, Any]] = []
    for g in groups:
        valid_members: List[Dict[str, Any]] = []
        for m in g.get("members") or []:
            sec = str(m.get("section", ""))
            idx = int(m.get("index", -1))
            items = section_items(story_bible, sec)
            if idx < 0 or idx >= len(items):
                continue
            label = str(m.get("label", ""))
            actual = items[idx]
            if label.strip() == actual.strip() or bible_match_score(label, actual) >= min_label_score:
                valid_members.append(m)
        if len(valid_members) >= 2:
            g = dict(g)
            g["members"] = valid_members
            keep_idx = int(g.get("suggested_keep_index", valid_members[0]["index"]))
            if not any(m["index"] == keep_idx and m["section"] == g.get("section") for m in valid_members):
                longest = max(valid_members, key=lambda m: len(str(m.get("label", ""))))
                g["section"] = longest["section"]
                g["suggested_keep_index"] = longest["index"]
            out.append(g)
    return out


def prune_bible_suggestion_groups(
    groups: List[Dict[str, Any]],
    affected_member_ids: set[str],
) -> List[Dict[str, Any]]:
    """Remove suggestion groups touched by a merge."""

    def touched(g: Dict[str, Any]) -> bool:
        ids = {str(m.get("id", "")) for m in g.get("members") or []}
        return bool(ids & affected_member_ids)

    return [g for g in groups if not touched(g)]


def auto_dedupe_bible(
    story_bible: Dict[str, Any],
    *,
    min_score: float = 0.92,
) -> List[str]:
    """Merge all high-confidence duplicate groups in place."""
    log: List[str] = []
    for group in find_bible_duplicate_groups(story_bible, min_score=min_score):
        merge_indices = [
            m["index"] for m in group.members
            if m["index"] != group.suggested_keep_index
        ]
        if merge_indices:
            sec_log, _ = apply_bible_dedupe_group(
                story_bible,
                section=group.section,
                keep_index=group.suggested_keep_index,
                merge_indices=merge_indices,
            )
            log.extend(sec_log)
    return log


def ai_suggest_bible_duplicate_groups(
    story_bible: Dict[str, Any],
    llm,
) -> List[BibleDuplicateGroup]:
    """Use LLM to find semantic duplicates across bible sections."""
    refs = collect_bible_items(story_bible)
    if len(refs) < 2:
        return []

    payload = [{"section": r.section, "index": r.index, "text": r.text[:300]} for r in refs]
    prompt = f"""You are a story-bible deduplication assistant.

These lines come from a novel project's story bible (themes, setting, premise beats, notes, etc.).
Identify groups that express the **same fact or idea** — including exact duplicates and near-paraphrases.

Items:
{json.dumps(payload, indent=2)}

Respond with ONLY valid JSON (no markdown fences):
{{
  "bible_groups": [
    {{
      "keep_section": "section key",
      "keep_index": 0,
      "merge_members": [{{"section": "...", "index": 1}}],
      "reason": "brief reason",
      "confidence": 0.95
    }}
  ]
}}

Rules:
- Only group items that are clearly redundant (same meaning).
- keep_section/keep_index should point at the clearest, most complete line.
- merge_members lists the redundant copies to remove (not including keep).
- omit empty bible_groups if none.
- confidence 0.0–1.0
"""
    raw = llm.complete("You output strict JSON only.", prompt)
    from state_parser import parse_json_object  # noqa: WPS433

    try:
        data = parse_json_object(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"AI bible dedup returned invalid JSON: {e}") from e

    ref_map = {(r.section, r.index): r for r in refs}
    out: List[BibleDuplicateGroup] = []
    for item in data.get("bible_groups") or []:
        keep_sec = str(item.get("keep_section", ""))
        keep_idx = int(item.get("keep_index", -1))
        if (keep_sec, keep_idx) not in ref_map:
            continue
        members = [
            {
                "section": keep_sec,
                "index": keep_idx,
                "label": ref_map[(keep_sec, keep_idx)].text,
                "id": f"{keep_sec}:{keep_idx}",
            }
        ]
        for m in item.get("merge_members") or []:
            sec = str(m.get("section", ""))
            idx = int(m.get("index", -1))
            if (sec, idx) not in ref_map:
                continue
            r = ref_map[(sec, idx)]
            members.append({
                "section": sec,
                "index": idx,
                "label": r.text,
                "id": f"{sec}:{idx}",
            })
        if len(members) < 2:
            continue
        out.append(
            BibleDuplicateGroup(
                section=keep_sec,
                confidence=float(item.get("confidence", 0.85)),
                reason=str(item.get("reason", "AI suggested merge")),
                suggested_keep_index=keep_idx,
                members=members,
            )
        )
    return out
