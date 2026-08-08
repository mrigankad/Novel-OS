"""Ranked chapter context packs for agent prompts.

Filter then budget — never dump the whole Codex and chop mid-string.
See docs/superpowers/specs/2026-08-04-context-pack-hosted-db-design.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Set

PackPurpose = Literal["architect", "scribe", "guardian", "continue", "consequence"]

PURPOSE_BUDGETS: Dict[PackPurpose, int] = {
    "architect": 5000,
    "scribe": 6000,
    "guardian": 7000,
    "continue": 3000,
    "consequence": 2500,
}

HOSTILE_LABELS = frozenset({"enemy", "rival", "enemies", "rivals"})


@dataclass
class ContextPack:
    chapter: int
    purpose: PackPurpose
    cast: List[Dict[str, Any]] = field(default_factory=list)
    bonds: List[Dict[str, Any]] = field(default_factory=list)
    threads: List[Dict[str, Any]] = field(default_factory=list)
    prior_chapters: List[Dict[str, Any]] = field(default_factory=list)
    codex: List[Dict[str, Any]] = field(default_factory=list)
    budgets: Dict[str, int] = field(default_factory=dict)
    dropped: List[Dict[str, str]] = field(default_factory=list)


def slice_chapter_for_llm(
    text: str,
    *,
    soft_limit: int = 12000,
    head: int = 6000,
    tail: int = 4000,
) -> str:
    """Full chapter if short; otherwise head + tail with an omission marker."""
    body = text or ""
    if len(body) <= soft_limit:
        return body
    omitted = len(body) - head - tail
    return (
        body[:head]
        + f"\n\n[… {omitted} characters omitted from mid-chapter …]\n\n"
        + body[-tail:]
    )


def build_context_pack(
    state: Any,
    chapter: int,
    *,
    purpose: PackPurpose,
    chapter_text: str | None = None,
) -> ContextPack:
    """Build a ranked pack for `chapter` from `StoryState`.

    Optional `chapter_text` (Guardian) pulls named cast from prose so 1-hop
    neighborhood covers people actually on the page.
    """
    pack = ContextPack(chapter=chapter, purpose=purpose)
    budget = PURPOSE_BUDGETS[purpose]
    pack.budgets = {"max_chars": budget, "used_chars": 0}

    ch = state.get_chapter(chapter) if hasattr(state, "get_chapter") else None
    hint_text = _chapter_hint_text(state, chapter, ch)
    if chapter_text:
        hint_text = f"{hint_text}\n{chapter_text[:8000]}"

    cast_map: Dict[str, Dict[str, Any]] = {}

    def add_cast(cid: str, name: str, role: str, why: str, rank: int) -> None:
        prev = cast_map.get(cid)
        if prev is None or rank > prev["rank"]:
            cast_map[cid] = {
                "id": cid,
                "name": name,
                "role": role or "",
                "why": why,
                "rank": rank,
            }

    # 1) POV
    pov_name = (getattr(ch, "pov_character", None) or "").strip() if ch else ""
    if pov_name:
        pov = _find_character_by_name(state, pov_name)
        if pov:
            add_cast(pov.id, pov.full_name, pov.role, "pov", 100)
        else:
            add_cast(f"name:{pov_name.lower()}", pov_name, "", "pov", 95)

    # 2) Named in outline/synopsis/hint
    for char in state.get_all_characters():
        if _name_in_text(char.full_name, hint_text):
            add_cast(char.id, char.full_name, char.role, "mentioned", 85)

    # characters_present on chapter
    if ch and getattr(ch, "characters_present", None):
        for token in ch.characters_present:
            found = state.characters.get(token) or _find_character_by_name(state, token)
            if found:
                add_cast(found.id, found.full_name, found.role, "present", 90)

    # 3) Recent appearances (window = 5)
    for char in state.get_all_characters():
        if char.last_appearance_chapter >= max(0, chapter - 5):
            add_cast(char.id, char.full_name, char.role, "recent", 70)

    # 4) One-hop relationship neighbors (Guardian: always expand from present/POV seeds)
    seed_ids = {cid for cid in cast_map if not str(cid).startswith("name:")}
    if purpose == "guardian" and not seed_ids and ch and ch.pov_character:
        pov = _find_character_by_name(state, ch.pov_character)
        if pov:
            seed_ids.add(pov.id)
    rels = getattr(state, "relationships", None) or {}
    for edge in rels.values():
        if edge.source_id in seed_ids:
            other = state.characters.get(edge.target_id)
            if other:
                boost = 25 if purpose == "guardian" else 0
                boost += 20 if edge.label.lower() in HOSTILE_LABELS else 0
                add_cast(other.id, other.full_name, other.role, "neighborhood", 75 + boost)
        if edge.target_id in seed_ids:
            other = state.characters.get(edge.source_id)
            if other:
                boost = 25 if purpose == "guardian" else 0
                boost += 20 if edge.label.lower() in HOSTILE_LABELS else 0
                add_cast(other.id, other.full_name, other.role, "neighborhood", 75 + boost)

    pack.cast = sorted(cast_map.values(), key=lambda x: (-x["rank"], x["name"].lower()))
    cast_ids = {c["id"] for c in pack.cast if not str(c["id"]).startswith("name:")}

    # Bonds
    bonds: List[Dict[str, Any]] = []
    for edge in rels.values():
        if edge.source_id not in cast_ids and edge.target_id not in cast_ids:
            continue
        rank = 80
        if edge.label.lower() in HOSTILE_LABELS:
            rank = 95
        if purpose == "guardian":
            rank += 5
        a = state.characters.get(edge.source_id)
        b = state.characters.get(edge.target_id)
        bonds.append({
            "id": edge.id,
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "source_name": a.full_name if a else edge.source_id,
            "target_name": b.full_name if b else edge.target_id,
            "label": edge.label,
            "status": edge.status,
            "rank": rank,
            "notes": (edge.notes or "")[:160],
        })
    pack.bonds = sorted(bonds, key=lambda x: (-x["rank"], x["label"].lower()))

    # Threads
    threads: List[Dict[str, Any]] = []
    active = list(state.get_active_plot_threads())
    if purpose == "guardian":
        for t in state.plot_threads.values():
            if t.status == "foreshadowed" and t not in active:
                active.append(t)
    cast_names = {c["name"].lower() for c in pack.cast}
    for t in active:
        rank = 50 + int(t.priority or 0) * 10
        related = set(t.related_characters or [])
        if related & cast_ids:
            rank += 15
        desc = (t.description or "").lower()
        if any(n in desc or n in (t.name or "").lower() for n in cast_names if len(n) >= 3):
            rank += 10
        if t.priority >= 3:
            rank += 5
        threads.append({
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "priority": t.priority,
            "description": (t.description or "")[:200],
            "rank": rank,
        })
    pack.threads = sorted(threads, key=lambda x: (-x["rank"], -x["priority"], x["name"].lower()))

    # Prior chapters
    pack.prior_chapters = _prior_chapters(state, chapter, count=2)

    # Codex (non-character)
    codex_items: List[Dict[str, Any]] = []
    for entry in getattr(state, "get_codex_entries", lambda: [])():
        rank = 40
        if _name_in_text(entry.name, hint_text):
            rank = 80
        for prior in pack.prior_chapters:
            if _name_in_text(entry.name, prior.get("synopsis") or ""):
                rank = max(rank, 65)
        # World rules get a mild boost for guardian
        if entry.entry_type == "worldbuilding" and purpose == "guardian":
            rank = max(rank, 55)
        codex_items.append({
            "id": entry.id,
            "entry_type": entry.entry_type,
            "name": entry.name,
            "summary": (entry.summary or "")[:320],
            "rank": rank,
        })
    pack.codex = sorted(codex_items, key=lambda x: (-x["rank"], x["name"].lower()))

    # Apply budget by dropping lowest-rank items from codex then threads then remote cast
    _apply_budget(pack, budget)
    return pack


def format_context_pack(pack: ContextPack, *, max_chars: int | None = None) -> str:
    """Render pack as markdown for prompts."""
    limit = max_chars if max_chars is not None else pack.budgets.get("max_chars") or PURPOSE_BUDGETS.get(pack.purpose, 5000)
    # Re-budget if caller tightens max_chars
    if max_chars is not None and max_chars < pack.budgets.get("max_chars", max_chars):
        _apply_budget(pack, max_chars)

    lines: List[str] = [
        f"## Context pack (chapter {pack.chapter}, {pack.purpose})",
        "",
    ]
    if pack.prior_chapters:
        lines.append("### Prior chapters")
        for p in pack.prior_chapters:
            syn = (p.get("synopsis") or "").strip() or "(no synopsis)"
            lines.append(f"- **Ch {p['number']}** {p.get('title') or ''}: {syn}")
        lines.append("")

    if pack.cast:
        lines.append("### Cast")
        for c in pack.cast:
            bits = [f"**{c['name']}**"]
            if c.get("role"):
                bits.append(f"({c['role']})")
            bits.append(f"[{c.get('why', '')}]")
            lines.append("- " + " ".join(bits))
        lines.append("")

    if pack.bonds:
        lines.append("### Relationships")
        for b in pack.bonds:
            an = b.get("source_name") or b["source_id"]
            bn = b.get("target_name") or b["target_id"]
            lines.append(
                f"- **{an}** ↔ **{bn}** ({b['label']}"
                f"{', ' + b['status'] if b.get('status') and b['status'] != 'active' else ''})"
            )
            if b.get("notes"):
                lines.append(f"  notes: {b['notes']}")
        lines.append("")

    if pack.threads:
        lines.append("### Plot threads")
        for t in pack.threads:
            lines.append(f"- **{t['name']}** (p{t['priority']}, {t['status']}): {t.get('description', '')}")
        lines.append("")

    if pack.codex:
        lines.append("### Codex")
        for e in pack.codex:
            line = f"- **{e['name']}** ({e['entry_type']})"
            if e.get("summary"):
                line += f": {e['summary']}"
            lines.append(line)
        lines.append("")

    if pack.dropped:
        lines.append(f"_(dropped {len(pack.dropped)} lower-rank items to fit budget)_")
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    pack.budgets["used_chars"] = len(text)
    # Soft safety: if still over, trim codex block only by removing trailing Codex lines
    if len(text) > limit:
        text = text[: limit - 40].rstrip() + "\n…[context pack truncated]\n"
        pack.budgets["used_chars"] = len(text)
    return text


def _apply_budget(pack: ContextPack, budget: int) -> None:
    """Drop lowest-rank codex, then threads, then low-rank cast until format fits budget."""
    # Estimate by iterative format — start by dropping low-rank codex
    pack.dropped = []

    def estimate() -> int:
        return len(format_context_pack_raw(pack))

    # Use a raw formatter without re-entering budget
    while estimate() > budget and pack.codex:
        victim = pack.codex.pop()  # already sorted high→low; pop last = lowest
        pack.dropped.append({"kind": "codex", "id": str(victim.get("id")), "reason": "over_budget"})
    while estimate() > budget and len(pack.threads) > 3:
        victim = pack.threads.pop()
        pack.dropped.append({"kind": "thread", "id": str(victim.get("id")), "reason": "over_budget"})
    while estimate() > budget and len(pack.cast) > 2:
        # Drop lowest rank that is not pov
        non_pov = [c for c in pack.cast if c.get("why") != "pov"]
        if not non_pov:
            break
        victim = min(non_pov, key=lambda c: c["rank"])
        pack.cast = [c for c in pack.cast if c["id"] != victim["id"]]
        pack.dropped.append({"kind": "cast", "id": str(victim.get("id")), "reason": "over_budget"})


def format_context_pack_raw(pack: ContextPack) -> str:
    """Format without mutating budgets/dropped (for size estimates)."""
    lines: List[str] = [f"## Context pack (chapter {pack.chapter}, {pack.purpose})", ""]
    if pack.prior_chapters:
        lines.append("### Prior chapters")
        for p in pack.prior_chapters:
            lines.append(f"- **Ch {p['number']}** {p.get('title') or ''}: {p.get('synopsis') or ''}")
        lines.append("")
    if pack.cast:
        lines.append("### Cast")
        for c in pack.cast:
            lines.append(f"- **{c['name']}** ({c.get('role') or ''}) [{c.get('why')}]")
        lines.append("")
    if pack.bonds:
        lines.append("### Relationships")
        for b in pack.bonds:
            lines.append(f"- {b['source_id']} ↔ {b['target_id']} ({b['label']})")
        lines.append("")
    if pack.threads:
        lines.append("### Plot threads")
        for t in pack.threads:
            lines.append(f"- **{t['name']}**: {t.get('description', '')}")
        lines.append("")
    if pack.codex:
        lines.append("### Codex")
        for e in pack.codex:
            lines.append(f"- **{e['name']}**: {e.get('summary') or ''}")
        lines.append("")
    return "\n".join(lines)


def _chapter_hint_text(state: Any, chapter: int, ch: Any) -> str:
    parts: List[str] = []
    if ch:
        parts.extend([
            ch.title or "",
            ch.pov_character or "",
            ch.location or "",
            " ".join(ch.plot_advances or []),
            " ".join(ch.emotional_beats or []),
        ])
    # Binder synopsis
    binder = getattr(state, "binder", None)
    if binder is not None and hasattr(binder, "chapter_node"):
        node = binder.chapter_node(chapter)
        if node is not None:
            parts.append(getattr(node, "synopsis", "") or "")
            parts.append(getattr(node, "title", "") or "")
    return "\n".join(parts)


def _prior_chapters(state: Any, chapter: int, count: int = 2) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for n in range(chapter - 1, max(0, chapter - count - 1), -1):
        if n < 1:
            continue
        prev = state.get_chapter(n)
        title = prev.title if prev else ""
        pov = prev.pov_character if prev else ""
        synopsis = ""
        binder = getattr(state, "binder", None)
        if binder is not None and hasattr(binder, "chapter_node"):
            node = binder.chapter_node(n)
            if node is not None:
                synopsis = (getattr(node, "synopsis", None) or "").strip()
                if not title:
                    title = getattr(node, "title", "") or ""
        if not synopsis:
            bits = [b for b in [title, f"POV {pov}" if pov else ""] if b]
            synopsis = " · ".join(bits) if bits else f"Chapter {n}"
        out.append({"number": n, "title": title, "synopsis": synopsis})
    return out


def _find_character_by_name(state: Any, name: str) -> Any:
    needle = (name or "").strip().lower()
    if not needle:
        return None
    for char in state.get_all_characters():
        if char.full_name.lower() == needle:
            return char
    return None


def _name_in_text(name: str, text: str) -> bool:
    n = (name or "").strip()
    if len(n) < 3:
        return False
    return n.lower() in (text or "").lower()
