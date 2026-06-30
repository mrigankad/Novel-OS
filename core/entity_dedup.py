"""
Detect and merge duplicate characters and plot threads.

Used by the importer (prevent duplicates) and the Resolve Duplicates UI.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import StoryState


_PAREN_RE = re.compile(r"\([^)]*\)")
_FORMERLY_RE = re.compile(r"formerly\s+(\w+)", re.IGNORECASE)
_PLOT_STOP = frozenset({
    "the", "a", "an", "and", "of", "to", "in", "for", "with", "s", "thread", "arc",
})


@dataclass
class DuplicateGroup:
    kind: str  # character | plot_thread
    confidence: float
    reason: str
    suggested_keep_id: str
    members: List[Dict[str, Any]]


def canonical_name(name: str) -> str:
    """Strip parentheticals and normalize whitespace."""
    n = _PAREN_RE.sub("", name).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def name_aliases(name: str) -> set[str]:
    """Tokens and alias strings for matching."""
    aliases: set[str] = set()
    raw = name.strip().lower()
    if raw:
        aliases.add(raw)
    base = canonical_name(name).lower()
    if base:
        aliases.add(base)
        aliases.update(base.split())
    for token in re.findall(r"[a-zA-Z']+", name.lower()):
        if len(token) > 1:
            aliases.add(token)
    m = _FORMERLY_RE.search(name)
    if m:
        aliases.add(m.group(1).lower())
    inner = re.search(r"\(([^)]+)\)", name)
    if inner:
        inner_text = inner.group(1).lower()
        aliases.add(inner_text)
        for token in re.findall(r"[a-zA-Z']+", inner_text):
            if token not in ("formerly", "deceased", "baby", "minor"):
                aliases.add(token)
    return aliases


def character_match_score(a: str, b: str) -> float:
    """0–1 similarity between two character names."""
    if not a.strip() or not b.strip():
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0
    ca, cb = canonical_name(a).lower(), canonical_name(b).lower()
    if ca == cb:
        return 0.96
    aa, ab = name_aliases(a), name_aliases(b)
    if aa & ab:
        ta, tb = set(ca.split()), set(cb.split())
        if len(ta) == 1 and ta <= tb:
            return 0.9
        if len(tb) == 1 and tb <= ta:
            return 0.9
        if ta and tb and (ta <= tb or tb <= ta):
            return 0.88
        inter = ta & tb
        union = ta | tb
        if inter:
            j = len(inter) / len(union)
            if j >= 0.34:
                return 0.72 + 0.25 * j
    return 0.0


def normalize_plot_name(name: str) -> str:
    n = canonical_name(name).lower()
    tokens = [t for t in re.findall(r"[a-z0-9']+", n) if t not in _PLOT_STOP]
    return " ".join(tokens)


def plot_match_score(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0
    na, nb = normalize_plot_name(a), normalize_plot_name(b)
    if na == nb:
        return 0.95
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    if ta <= tb or tb <= ta:
        return 0.85
    inter = ta & tb
    if not inter:
        return 0.0
    j = len(inter) / len(ta | tb)
    return 0.65 + 0.3 * j if j >= 0.4 else j


def find_matching_character(
    state: "StoryState", name: str, *, min_score: float = 0.85,
) -> Optional[str]:
    best_id: Optional[str] = None
    best = min_score
    needle = name.strip().lower()
    if not needle:
        return None
    # Exact full name or registered alias
    direct = state.get_character_by_name(name)
    if direct:
        return direct.id
    for char in state.characters.values():
        for label in char.all_names():
            score = character_match_score(name, label)
            if score > best:
                best = score
                best_id = char.id
    return best_id


def register_name_as_alias(state: "StoryState", character_id: str, seen_name: str) -> bool:
    """If seen_name differs from the character's canonical name, store it as an alias."""
    char = state.characters.get(character_id)
    if char is None:
        return False
    seen = seen_name.strip()
    if not seen:
        return False
    if seen.lower() == char.full_name.lower():
        return False
    if character_match_score(seen, char.full_name) >= 0.96:
        return False
    return state.add_character_alias(character_id, seen)


def find_matching_plot_thread(
    state: "StoryState", name: str, *, min_score: float = 0.78,
) -> Optional[str]:
    best_id: Optional[str] = None
    best = min_score
    for thread in state.plot_threads.values():
        score = plot_match_score(name, thread.name)
        if score > best:
            best = score
            best_id = thread.id
    return best_id


def _main_plot_threads(state: "StoryState"):
    mains = [t for t in state.plot_threads.values() if t.thread_type == "main"]
    if mains:
        return mains
    # No explicit mains yet — treat highest-priority active thread as parent candidate.
    active = state.get_active_plot_threads()
    return active if active else list(state.plot_threads.values())


def format_subplot_line(name: str, description: str = "") -> str:
    name = name.strip()
    desc = (description or "").strip()
    if not name:
        return desc
    if not desc or desc.lower() == name.lower():
        return name
    return f"{name}: {desc}"


def subplot_head(line: str) -> str:
    """Label before ':' in a stored subplot line, or the whole line."""
    line = line.strip()
    if not line:
        return ""
    return line.split(":", 1)[0].strip()


def match_subplot_index(
    lines: List[str],
    query: str,
    *,
    min_score: float = 0.72,
) -> Optional[int]:
    """Index of the subplot line matching query (name or full line), if any."""
    query = query.strip()
    if not query:
        return None
    qn = query.lower()
    for i, line in enumerate(lines):
        if line.strip().lower() == qn:
            return i
    best_i: Optional[int] = None
    best = min_score
    for i, line in enumerate(lines):
        head = subplot_head(line)
        score = max(
            plot_match_score(query, head),
            plot_match_score(query, line),
        )
        if score > best:
            best = score
            best_i = i
    return best_i


def find_parent_plot_thread(
    state: "StoryState",
    *,
    parent_hint: str = "",
    subplot_name: str = "",
    description: str = "",
    related_char_ids: Optional[List[str]] = None,
    min_score: float = 0.72,
) -> Optional[str]:
    """Pick the major plot thread that should own a related subplot."""
    hint = parent_hint.strip()
    if hint:
        tid = find_matching_plot_thread(state, hint, min_score=0.68)
        if tid:
            return tid

    mains = _main_plot_threads(state)
    if not mains:
        return None

    related_char_ids = related_char_ids or []
    if related_char_ids:
        best_id: Optional[str] = None
        best_overlap = 0
        for thread in mains:
            overlap = len(set(thread.related_characters) & set(related_char_ids))
            if overlap > best_overlap:
                best_overlap = overlap
                best_id = thread.id
        if best_id and best_overlap > 0:
            return best_id

    probe = subplot_name.strip() or description.strip()
    if probe:
        best_id = None
        best = min_score
        for thread in mains:
            score = plot_match_score(probe, thread.name)
            if description.strip():
                score = max(score, plot_match_score(description, thread.name) * 0.9)
            if score > best:
                best = score
                best_id = thread.id
        if best_id:
            return best_id

    if len(mains) == 1:
        return mains[0].id
    return None


def _union_find_groups(pairs: List[tuple[str, str]]) -> List[List[str]]:
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in pairs:
        union(a, b)
    groups: Dict[str, List[str]] = {}
    for node in parent:
        root = find(node)
        groups.setdefault(root, []).append(node)
    return [g for g in groups.values() if len(g) > 1]


def _character_richness(state: "StoryState", cid: str) -> int:
    c = state.characters[cid]
    score = len(c.full_name) * 2
    if c.role == "protagonist":
        score += 50
    elif c.role == "antagonist":
        score += 30
    for field in (
        c.notes, c.physical_description, c.internal_desire, c.external_goal,
        c.fear, c.weakness, c.strength, c.secret, c.current_location,
    ):
        if field:
            score += 5
    if c.last_appearance_chapter:
        score += 2
    return score


def _pick_character_keep(state: "StoryState", ids: List[str]) -> str:
    return max(ids, key=lambda cid: _character_richness(state, cid))


def _pick_plot_keep(state: "StoryState", ids: List[str]) -> str:
    def richness(tid: str) -> int:
        t = state.plot_threads[tid]
        s = len(t.name) + len(t.description or "")
        if t.related_characters:
            s += len(t.related_characters) * 3
        if t.milestones:
            s += len(t.milestones) * 2
        return s
    return max(ids, key=richness)


def find_character_duplicate_groups(
    state: "StoryState", *, min_score: float = 0.85,
) -> List[DuplicateGroup]:
    chars = list(state.characters.values())
    pairs: List[tuple[str, str, float]] = []
    for i, a in enumerate(chars):
        for b in chars[i + 1:]:
            score = character_match_score(a.full_name, b.full_name)
            if score >= min_score:
                pairs.append((a.id, b.id, score))
    raw_groups = _union_find_groups([(a, b) for a, b, _ in pairs])
    score_map = {(a, b): s for a, b, s in pairs}
    score_map.update({(b, a): s for a, b, s in pairs})
    out: List[DuplicateGroup] = []
    for g in raw_groups:
        keep = _pick_character_keep(state, g)
        confs = []
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                confs.append(score_map.get((a, b), 0.85))
        confidence = max(confs) if confs else 0.85
        names = [state.characters[cid].full_name for cid in g]
        reason = f"Names match as the same person: {', '.join(names)}"
        out.append(DuplicateGroup(
            kind="character",
            confidence=round(confidence, 2),
            reason=reason,
            suggested_keep_id=keep,
            members=[
                {
                    "id": cid,
                    "label": state.characters[cid].full_name,
                    "role": state.characters[cid].role,
                }
                for cid in g
            ],
        ))
    out.sort(key=lambda x: (-x.confidence, x.members[0]["label"]))
    return out


def find_plot_duplicate_groups(
    state: "StoryState", *, min_score: float = 0.78,
) -> List[DuplicateGroup]:
    threads = list(state.plot_threads.values())
    pairs: List[tuple[str, str, float]] = []
    for i, a in enumerate(threads):
        for b in threads[i + 1:]:
            score = plot_match_score(a.name, b.name)
            if score >= min_score:
                pairs.append((a.id, b.id, score))
    raw_groups = _union_find_groups([(a, b) for a, b, _ in pairs])
    score_map = {(a, b): s for a, b, s in pairs}
    score_map.update({(b, a): s for a, b, s in pairs})
    out: List[DuplicateGroup] = []
    for g in raw_groups:
        keep = _pick_plot_keep(state, g)
        confs = [score_map.get((a, b), 0.78) for i, a in enumerate(g) for b in g[i + 1:]]
        confidence = max(confs) if confs else 0.78
        names = [state.plot_threads[tid].name for tid in g]
        out.append(DuplicateGroup(
            kind="plot_thread",
            confidence=round(confidence, 2),
            reason=f"Similar plot threads: {', '.join(names)}",
            suggested_keep_id=keep,
            members=[
                {
                    "id": tid,
                    "label": state.plot_threads[tid].name,
                    "thread_type": state.plot_threads[tid].thread_type,
                }
                for tid in g
            ],
        ))
    out.sort(key=lambda x: (-x.confidence, x.members[0]["label"]))
    return out


def scan_duplicates(
    state: "StoryState",
    *,
    character_threshold: float = 0.85,
    plot_threshold: float = 0.78,
    include_plot_panel: bool = True,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "characters": find_character_duplicate_groups(state, min_score=character_threshold),
        "plot_threads": find_plot_duplicate_groups(state, min_score=plot_threshold),
    }
    if include_plot_panel:
        out["plot_panel_issues"] = find_plot_panel_issues(state)
    return out


_NON_MAIN_PLOT_TYPES = frozenset({"subplot", "character_arc", "mystery"})


@dataclass
class PlotPanelIssue:
    """Cross-field plot/subplot duplication on the plots page."""
    issue_id: str
    kind: str
    confidence: float
    reason: str
    subplot_line: str
    locations: List[Dict[str, Any]] = field(default_factory=list)
    thread_id: Optional[str] = None
    thread_name: Optional[str] = None
    suggested_parent_id: str = ""
    suggested_parent_name: str = ""
    suggested_action: str = "remove_duplicates"


def _plot_panel_issue_id(kind: str, *parts: str) -> str:
    payload = "|".join([kind, *parts])
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _subplot_location(parent_id: str, parent_name: str, index: int, line: str) -> Dict[str, Any]:
    return {
        "parent_id": parent_id,
        "parent_name": parent_name,
        "index": index,
        "line": line,
    }


def _pick_subplot_parent(
    state: "StoryState",
    line: str,
    candidate_parent_ids: List[str],
) -> str:
    head = subplot_head(line)
    desc = line.split(":", 1)[1].strip() if ":" in line else ""
    hint = find_parent_plot_thread(
        state,
        subplot_name=head,
        description=desc,
        min_score=0.68,
    )
    if hint and hint in candidate_parent_ids:
        return hint
    return _pick_plot_keep(state, candidate_parent_ids)


def find_plot_panel_issues(
    state: "StoryState",
    *,
    min_score: float = 0.78,
) -> List[PlotPanelIssue]:
    """Detect duplicate/misplaced subplots across plot threads on the plots page."""
    issues: List[PlotPanelIssue] = []
    seen_ids: set[str] = set()

    def add(issue: PlotPanelIssue) -> None:
        if issue.issue_id in seen_ids:
            return
        seen_ids.add(issue.issue_id)
        issues.append(issue)

    # Duplicate subplot lines within the same thread.
    for thread in state.plot_threads.values():
        lines = thread.subplots
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                a, b = lines[i].strip(), lines[j].strip()
                if not a or not b:
                    continue
                score = max(
                    plot_match_score(a, b),
                    plot_match_score(subplot_head(a), subplot_head(b)),
                )
                if score < min_score:
                    continue
                issue_id = _plot_panel_issue_id(
                    "duplicate_subplot_within", thread.id, str(i), str(j),
                )
                add(PlotPanelIssue(
                    issue_id=issue_id,
                    kind="duplicate_subplot_within",
                    confidence=round(score, 2),
                    reason=f'Duplicate subplot lines on "{thread.name}"',
                    subplot_line=a if len(a) >= len(b) else b,
                    locations=[
                        _subplot_location(thread.id, thread.name, i, lines[i]),
                        _subplot_location(thread.id, thread.name, j, lines[j]),
                    ],
                    suggested_parent_id=thread.id,
                    suggested_parent_name=thread.name,
                    suggested_action="remove_duplicates",
                ))

    # Same subplot under multiple parents.
    by_head: Dict[str, List[tuple[str, str, int, str]]] = {}
    for thread in state.plot_threads.values():
        for i, line in enumerate(thread.subplots):
            text = line.strip()
            if not text:
                continue
            head = subplot_head(text)
            key = normalize_plot_name(head) or head.lower()
            by_head.setdefault(key, []).append((thread.id, thread.name, i, text))

    for key, locs in by_head.items():
        parent_ids = {loc[0] for loc in locs}
        if len(parent_ids) < 2:
            continue
        line = max((loc[3] for loc in locs), key=len)
        keep_id = _pick_subplot_parent(state, line, list(parent_ids))
        keep_name = state.plot_threads[keep_id].name
        scores: List[float] = []
        for a in range(len(locs)):
            for b in range(a + 1, len(locs)):
                scores.append(plot_match_score(locs[a][3], locs[b][3]))
        confidence = max(scores) if scores else min_score
        parents = ", ".join(sorted({loc[1] for loc in locs}))
        issue_id = _plot_panel_issue_id("duplicate_subplot_across", key, *sorted(parent_ids))
        add(PlotPanelIssue(
            issue_id=issue_id,
            kind="duplicate_subplot_across",
            confidence=round(confidence, 2),
            reason=f'Subplot "{subplot_head(line)}" appears under multiple plots: {parents}',
            subplot_line=line,
            locations=[
                _subplot_location(pid, pname, idx, text)
                for pid, pname, idx, text in locs
            ],
            suggested_parent_id=keep_id,
            suggested_parent_name=keep_name,
            suggested_action="move_to_parent",
        ))

    # Top-level thread whose name matches a subplot on another thread.
    for thread in state.plot_threads.values():
        for other in state.plot_threads.values():
            if other.id == thread.id:
                continue
            for i, line in enumerate(other.subplots):
                head = subplot_head(line)
                score = plot_match_score(thread.name, head)
                if score < min_score:
                    continue
                issue_id = _plot_panel_issue_id(
                    "thread_under_wrong_parent", thread.id, other.id, str(i),
                )
                add(PlotPanelIssue(
                    issue_id=issue_id,
                    kind="thread_under_wrong_parent",
                    confidence=round(score, 2),
                    reason=(
                        f'Plot thread "{thread.name}" matches a subplot under "{other.name}" '
                        f"— likely nested under the wrong parent"
                    ),
                    subplot_line=line.strip(),
                    locations=[_subplot_location(other.id, other.name, i, line)],
                    thread_id=thread.id,
                    thread_name=thread.name,
                    suggested_parent_id=other.id,
                    suggested_parent_name=other.name,
                    suggested_action="nest_thread",
                ))

    # Subplot line whose head matches a different top-level thread.
    for thread in state.plot_threads.values():
        for i, line in enumerate(thread.subplots):
            head = subplot_head(line)
            if not head:
                continue
            match_id = find_matching_plot_thread(state, head, min_score=0.85)
            if not match_id or match_id == thread.id:
                continue
            match = state.plot_threads[match_id]
            score = plot_match_score(head, match.name)
            issue_id = _plot_panel_issue_id(
                "subplot_matches_thread", thread.id, match_id, str(i),
            )
            add(PlotPanelIssue(
                issue_id=issue_id,
                kind="subplot_matches_thread",
                confidence=round(score, 2),
                reason=(
                    f'Subplot "{head}" on "{thread.name}" matches separate plot thread '
                    f'"{match.name}" — nest the thread or remove the duplicate line'
                ),
                subplot_line=line.strip(),
                locations=[_subplot_location(thread.id, thread.name, i, line)],
                thread_id=match_id,
                thread_name=match.name,
                suggested_parent_id=thread.id,
                suggested_parent_name=thread.name,
                suggested_action="nest_thread",
            ))

    issues.sort(key=lambda x: (-x.confidence, x.reason))
    return issues


def _remove_subplot_at(state: "StoryState", parent_id: str, index: int) -> str:
    thread = state.plot_threads[parent_id]
    removed = thread.subplots.pop(index)
    return removed


def _apply_plot_panel_issue(state: "StoryState", issue: PlotPanelIssue) -> List[str]:
    log: List[str] = []
    if issue.kind == "duplicate_subplot_within":
        locs = sorted(issue.locations, key=lambda loc: loc["index"], reverse=True)
        keep_idx = max(issue.locations, key=lambda loc: len(loc["line"]))["index"]
        for loc in locs:
            idx = loc["index"]
            if idx == keep_idx:
                continue
            removed = _remove_subplot_at(state, issue.suggested_parent_id, idx)
            log.append(f'Removed duplicate subplot on {issue.suggested_parent_name}: {removed[:60]}')

    elif issue.kind == "duplicate_subplot_across":
        keep_id = issue.suggested_parent_id
        for loc in sorted(issue.locations, key=lambda x: x["index"], reverse=True):
            if loc["parent_id"] == keep_id:
                continue
            parent = state.plot_threads[loc["parent_id"]]
            idx = match_subplot_index(parent.subplots, loc["line"], min_score=0.95)
            if idx is None:
                idx = loc["index"]
            if 0 <= idx < len(parent.subplots):
                removed = parent.subplots.pop(idx)
                log.append(
                    f'Moved subplot off {loc["parent_name"]} (kept on {issue.suggested_parent_name}): '
                    f"{removed[:60]}",
                )

    elif issue.kind in ("thread_under_wrong_parent", "subplot_matches_thread"):
        if not issue.thread_id or not issue.suggested_parent_id:
            return log
        if issue.thread_id not in state.plot_threads:
            return log
        child = state.plot_threads[issue.thread_id]
        if issue.kind == "thread_under_wrong_parent" and child.thread_type == "main":
            # Do not auto-nest main threads — only remove duplicate subplot line.
            for loc in sorted(issue.locations, key=lambda x: x["index"], reverse=True):
                parent = state.plot_threads[loc["parent_id"]]
                idx = loc["index"]
                if 0 <= idx < len(parent.subplots):
                    removed = parent.subplots.pop(idx)
                    log.append(
                        f'Removed duplicate subplot from {loc["parent_name"]} '
                        f'(kept main thread "{child.name}"): {removed[:60]}',
                    )
            return log
        log.extend(nest_plot_threads(state, issue.suggested_parent_id, [issue.thread_id]))
        for loc in sorted(issue.locations, key=lambda x: x["index"], reverse=True):
            parent = state.plot_threads.get(loc["parent_id"])
            if parent is None:
                continue
            idx = match_subplot_index(parent.subplots, loc["line"], min_score=0.95)
            if idx is not None and subplot_head(parent.subplots[idx]).lower() == child.name.lower():
                removed = parent.subplots.pop(idx)
                log.append(f'Removed redundant subplot line after nesting: {removed[:60]}')

    if log:
        state._log_action("plot_panel_issue_resolved", {"issue_id": issue.issue_id, "kind": issue.kind})
    return log


def resolve_plot_panel_issue(
    state: "StoryState",
    issue_id: str,
    *,
    issues: Optional[List[PlotPanelIssue]] = None,
) -> List[str]:
    pool = issues if issues is not None else find_plot_panel_issues(state)
    for issue in pool:
        if issue.issue_id == issue_id:
            return _apply_plot_panel_issue(state, issue)
    raise ValueError(f"Unknown plot panel issue {issue_id!r}")


def auto_resolve_plot_panel_issues(
    state: "StoryState",
    *,
    min_score: float = 0.88,
    max_passes: int = 40,
) -> List[str]:
    log: List[str] = []
    for _ in range(max_passes):
        issues = [i for i in find_plot_panel_issues(state) if i.confidence >= min_score]
        if not issues:
            break
        log.extend(_apply_plot_panel_issue(state, issues[0]))
    return log


def merge_characters(
    state: "StoryState",
    keep_id: str,
    merge_ids: List[str],
    *,
    label_override: str = "",
) -> List[str]:
    """Merge merge_ids into keep_id. Returns change log."""
    from state_manager import Character  # noqa: WPS433

    log: List[str] = []
    if keep_id not in state.characters:
        raise ValueError(f"Unknown character {keep_id!r}")
    keep = state.characters[keep_id]
    for mid in merge_ids:
        if mid == keep_id:
            continue
        dup = state.characters.get(mid)
        if dup is None:
            continue
        keep_name_before = keep.full_name
        dup_name = dup.full_name
        # Prefer longer canonical name
        if len(dup_name) > len(keep_name_before):
            keep.full_name = dup_name
        if keep_name_before.lower() != keep.full_name.lower():
            state.add_character_alias(keep_id, keep_name_before)
        register_name_as_alias(state, keep_id, dup_name)
        # Role: keep higher priority
        role_rank = {"protagonist": 4, "antagonist": 3, "supporting": 2, "minor": 1}
        if role_rank.get(dup.role, 0) > role_rank.get(keep.role, 0):
            keep.role = dup.role
        for field in (
            "physical_description", "internal_desire", "external_goal", "fear",
            "weakness", "strength", "secret", "current_location", "emotional_state",
        ):
            kv = getattr(keep, field)
            dv = getattr(dup, field)
            if not kv and dv:
                setattr(keep, field, dv)
        if dup.notes and dup.notes not in (keep.notes or ""):
            keep.notes = f"{keep.notes}\n{dup.notes}".strip() if keep.notes else dup.notes
        if dup.age and not keep.age:
            keep.age = dup.age
        keep.last_appearance_chapter = max(keep.last_appearance_chapter, dup.last_appearance_chapter)
        keep.arc_progress = max(keep.arc_progress, dup.arc_progress)
        for k, v in dup.relationships.items():
            keep.relationships.setdefault(k, v)
        for item in dup.knowledge:
            if item not in keep.knowledge:
                keep.knowledge.append(item)
        for item in dup.possessions:
            if item not in keep.possessions:
                keep.possessions.append(item)
        for alias in dup.aliases:
            state.add_character_alias(keep_id, alias)
        # Rewire references
        dup_names = {dup.full_name.lower(), canonical_name(dup.full_name).lower()}
        dup_names.update(a.lower() for a in dup.aliases)
        for ch in state.chapters.values():
            if ch.pov_character.lower() in dup_names:
                ch.pov_character = keep.full_name
        for thread in state.plot_threads.values():
            thread.related_characters = [
                keep_id if cid == mid else cid for cid in thread.related_characters
            ]
            thread.related_characters = list(dict.fromkeys(thread.related_characters))
        for other in state.characters.values():
            if mid in other.relationships:
                other.relationships[keep_id] = other.relationships.pop(mid)
        for event in state.timeline:
            event.characters_present = [
                keep_id if cid == mid else cid for cid in event.characters_present
            ]
        state.delete_character(mid)
        log.append(f"Merged {dup.full_name!r} → {keep.full_name!r}")
    override = label_override.strip()
    if override:
        old_names = {keep.full_name.lower(), *(a.lower() for a in keep.aliases)}
        if keep.full_name.lower() != override.lower():
            state.add_character_alias(keep_id, keep.full_name)
        keep.full_name = override
        for ch in state.chapters.values():
            if ch.pov_character.lower() in old_names:
                ch.pov_character = override
        log.append(f"Canonical name set to {override!r}")
    state._log_action("characters_merged", {"keep_id": keep_id, "merged": merge_ids})
    return log


def merge_plot_threads(
    state: "StoryState",
    keep_id: str,
    merge_ids: List[str],
    *,
    label_override: str = "",
) -> List[str]:
    log: List[str] = []
    if keep_id not in state.plot_threads:
        raise ValueError(f"Unknown plot thread {keep_id!r}")
    keep = state.plot_threads[keep_id]
    for mid in merge_ids:
        if mid == keep_id:
            continue
        dup = state.plot_threads.get(mid)
        if dup is None:
            continue
        if len(dup.name) > len(keep.name):
            keep.name = dup.name
        if dup.description and len(dup.description) > len(keep.description or ""):
            keep.description = dup.description
        keep.start_chapter = min(
            x for x in (keep.start_chapter, dup.start_chapter) if x
        ) if keep.start_chapter or dup.start_chapter else keep.start_chapter
        keep.last_updated_chapter = max(keep.last_updated_chapter, dup.last_updated_chapter)
        keep.priority = max(keep.priority, dup.priority)
        for cid in dup.related_characters:
            if cid not in keep.related_characters:
                keep.related_characters.append(cid)
        for tid in dup.related_threads:
            if tid not in keep.related_threads and tid != keep_id:
                keep.related_threads.append(tid)
        keep.milestones.extend(dup.milestones)
        keep.foreshadowing_planted = list(set(keep.foreshadowing_planted + dup.foreshadowing_planted))
        seen = {s.strip().lower() for s in keep.subplots if s.strip()}
        for sub in dup.subplots:
            key = sub.strip().lower()
            if key and key not in seen:
                keep.subplots.append(sub.strip())
                seen.add(key)
        for other in state.plot_threads.values():
            other.related_threads = [
                keep_id if tid == mid else tid for tid in other.related_threads
            ]
        state.delete_plot_thread(mid)
        log.append(f"Merged plot {dup.name!r} → {keep.name!r}")
    override = label_override.strip()
    if override:
        keep.name = override
        log.append(f"Canonical plot name set to {override!r}")
    state._log_action("plot_threads_merged", {"keep_id": keep_id, "merged": merge_ids})
    return log


def nest_plot_threads(
    state: "StoryState",
    parent_id: str,
    child_ids: List[str],
    *,
    label_override: str = "",
) -> List[str]:
    """Move child plot threads under parent as subplot lines; remove child threads."""
    log: List[str] = []
    if parent_id not in state.plot_threads:
        raise ValueError(f"Unknown plot thread {parent_id!r}")
    parent = state.plot_threads[parent_id]
    seen = {s.strip().lower() for s in parent.subplots if s.strip()}

    for cid in child_ids:
        if cid == parent_id:
            continue
        child = state.plot_threads.get(cid)
        if child is None:
            continue
        headline = child.name.strip()
        if child.description and child.description.strip() not in ("", child.name):
            headline = f"{child.name}: {child.description.strip()}"
        if headline.lower() not in seen:
            parent.subplots.append(headline)
            seen.add(headline.lower())
        for sub in child.subplots:
            sub = sub.strip()
            if sub and sub.lower() not in seen:
                parent.subplots.append(sub)
                seen.add(sub.lower())
        for rc in child.related_characters:
            if rc not in parent.related_characters:
                parent.related_characters.append(rc)
        for other in state.plot_threads.values():
            other.related_threads = [
                parent_id if tid == cid else tid for tid in other.related_threads
            ]
        child_name = child.name
        state.delete_plot_thread(cid)
        log.append(f"Nested {child_name!r} under {parent.name!r} as subplot")

    override = label_override.strip()
    if override:
        parent.name = override
        log.append(f"Parent plot name set to {override!r}")

    state._log_action("plot_threads_nested", {"parent_id": parent_id, "child_ids": child_ids})
    return log


def filter_stale_entity_groups(
    state: "StoryState",
    groups: List[Dict[str, Any]],
    kind: str,
) -> List[Dict[str, Any]]:
    """Drop AI/heuristic groups whose members no longer exist in live state."""
    id_map = state.characters if kind == "character" else state.plot_threads
    out: List[Dict[str, Any]] = []
    for g in groups:
        valid_members: List[Dict[str, Any]] = []
        for m in g.get("members") or []:
            mid = str(m.get("id", ""))
            if mid not in id_map:
                continue
            if kind == "character":
                c = id_map[mid]
                valid_members.append({
                    "id": mid,
                    "label": c.full_name,
                    "role": c.role,
                })
            else:
                t = id_map[mid]
                valid_members.append({
                    "id": mid,
                    "label": t.name,
                    "thread_type": t.thread_type,
                })
        if len(valid_members) < 2:
            continue
        g = dict(g)
        g["members"] = valid_members
        keep_id = str(g.get("suggested_keep_id", ""))
        valid_ids = {m["id"] for m in valid_members}
        if keep_id not in valid_ids:
            g["suggested_keep_id"] = valid_members[0]["id"]
        out.append(g)
    return out


def auto_resolve_duplicates(
    state: "StoryState",
    *,
    character_threshold: float = 0.9,
    plot_threshold: float = 0.88,
) -> List[str]:
    """Merge all high-confidence duplicate groups."""
    log: List[str] = []
    for group in find_character_duplicate_groups(state, min_score=character_threshold):
        merge_ids = [m["id"] for m in group.members if m["id"] != group.suggested_keep_id]
        if merge_ids:
            log.extend(merge_characters(state, group.suggested_keep_id, merge_ids))
    for group in find_plot_duplicate_groups(state, min_score=plot_threshold):
        merge_ids = [m["id"] for m in group.members if m["id"] != group.suggested_keep_id]
        if merge_ids:
            log.extend(merge_plot_threads(state, group.suggested_keep_id, merge_ids))
    return log


def ai_suggest_duplicate_groups(state: "StoryState", llm) -> Dict[str, List[DuplicateGroup]]:
    """Use LLM to suggest character/plot merge groups (local model only)."""
    chars = [
        {"id": c.id, "name": c.full_name, "role": c.role}
        for c in state.characters.values()
    ]
    plots = [
        {"id": t.id, "name": t.name, "type": t.thread_type}
        for t in state.plot_threads.values()
    ]
    if not chars and not plots:
        return {"characters": [], "plot_threads": []}

    prompt = f"""You are a story-bible deduplication assistant.

Given character and plot-thread lists from a novel project, identify groups that refer to the **same person** or the **same plot thread** under different names.

Characters:
{json.dumps(chars, indent=2)}

Plot threads:
{json.dumps(plots, indent=2)}

Respond with ONLY valid JSON (no markdown fences):
{{
  "character_groups": [
    {{"keep_id": "id to keep", "merge_ids": ["ids to merge into keep"], "reason": "brief reason", "confidence": 0.95}}
  ],
  "plot_groups": [
    {{"keep_id": "id", "merge_ids": ["..."], "reason": "...", "confidence": 0.9}}
  ]
}}

Rules:
- Only group entries that are clearly the same entity (e.g. "Nora" and "Nora Blake").
- pick keep_id as the most complete name/entry.
- omit empty arrays if none.
- confidence 0.0–1.0
"""
    raw = llm.complete(
        "You output strict JSON only.",
        prompt,
    )
    from state_parser import parse_json_object  # noqa: WPS433

    try:
        data = parse_json_object(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"AI duplicate scan returned invalid JSON: {e}") from e

    def _groups(items: list, kind: str) -> List[DuplicateGroup]:
        out: List[DuplicateGroup] = []
        id_map = (
            state.characters if kind == "character" else state.plot_threads
        )
        for item in items or []:
            keep_id = item.get("keep_id", "")
            merge_ids = item.get("merge_ids") or []
            if keep_id not in id_map:
                continue
            members_ids = [keep_id] + [m for m in merge_ids if m in id_map and m != keep_id]
            if len(members_ids) < 2:
                continue
            if kind == "character":
                members = [
                    {"id": cid, "label": state.characters[cid].full_name, "role": state.characters[cid].role}
                    for cid in members_ids
                ]
            else:
                members = [
                    {
                        "id": tid,
                        "label": state.plot_threads[tid].name,
                        "thread_type": state.plot_threads[tid].thread_type,
                    }
                    for tid in members_ids
                ]
            out.append(DuplicateGroup(
                kind=kind,
                confidence=float(item.get("confidence", 0.85)),
                reason=str(item.get("reason", "AI suggested merge")),
                suggested_keep_id=keep_id,
                members=members,
            ))
        return out

    return {
        "characters": _groups(
            data.get("character_groups") or data.get("character_duplicates") or [],
            "character",
        ),
        "plot_threads": _groups(
            data.get("plot_groups") or data.get("plot_thread_groups") or [],
            "plot_thread",
        ),
    }
