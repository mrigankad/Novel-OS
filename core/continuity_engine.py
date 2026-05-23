"""
Novel OS - Deterministic Continuity Engine

Runs FAST, FREE local checks before (and after) the LLM Continuity Guardian.
These catch the obvious errors no API call should ever be spent on, and surface
structured findings the Guardian agent can use as starting context.

Categories of checks:
  - dormant plot threads
  - unresolved foreshadowing past its target chapter
  - long-absent named characters
  - chapter file/status mismatches
  - characters appearing after a flagged death
  - plot threads marked active past their target_resolution_chapter
  - missing required character fields
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from state_manager import StoryState


# Tunables — keep conservative to avoid false positives.
DORMANT_THREAD_GAP_CHAPTERS = 3
ABSENT_CHARACTER_GAP_CHAPTERS = 5
DEAD_KEYWORDS = ("dead", "killed", "deceased", "died")


# --------------------------------------------------------------------- Finding

@dataclass
class Finding:
    severity: str          # "critical" | "warning" | "info"
    category: str          # short tag, e.g. "dormant_thread"
    message: str
    suggestion: str = ""
    chapter: Optional[int] = None
    entity_id: Optional[str] = None  # character_id, thread_id, etc.

    def format(self) -> str:
        head = f"[{self.severity.upper()}] {self.category}"
        if self.chapter is not None:
            head += f" (ch{self.chapter})"
        body = f"  {self.message}"
        tail = f"  -> {self.suggestion}" if self.suggestion else ""
        return "\n".join(p for p in (head, body, tail) if p)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------- checks

def _current_chapter(state: "StoryState") -> int:
    """The highest-numbered chapter that is at least drafted; 0 if none."""
    drafted = [
        c.number for c in state.chapters.values()
        if c.status in ("drafted", "editing", "edited", "validated", "complete")
    ]
    return max(drafted) if drafted else 0


def check_dormant_threads(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    out: List[Finding] = []
    for thread in state.plot_threads.values():
        if thread.status != "active":
            continue
        last_seen = thread.last_updated_chapter or thread.start_chapter or 0
        gap = cur - last_seen
        if gap > DORMANT_THREAD_GAP_CHAPTERS:
            out.append(Finding(
                severity="warning",
                category="dormant_thread",
                message=f"Plot thread '{thread.name}' (priority {thread.priority}) "
                        f"has not advanced in {gap} chapters (last touched ch{last_seen}).",
                suggestion="Touch this thread in the next chapter or mark it resolved/abandoned.",
                chapter=cur,
                entity_id=thread.id,
            ))
    return out


def check_overdue_threads(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    out: List[Finding] = []
    for thread in state.plot_threads.values():
        if thread.status != "active":
            continue
        target = thread.target_resolution_chapter
        if target and cur > target:
            out.append(Finding(
                severity="critical",
                category="overdue_thread",
                message=f"Plot thread '{thread.name}' was scheduled to resolve by ch{target}, "
                        f"current chapter is {cur} and it's still active.",
                suggestion="Resolve, abandon, or push target_resolution_chapter.",
                chapter=cur,
                entity_id=thread.id,
            ))
    return out


def check_unresolved_foreshadowing(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    """Foreshadowing planted in early chapters but never matched by a 'resolved' note."""
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    resolved_all: set = set()
    for ch in state.chapters.values():
        for r in ch.foreshadowing_resolved:
            resolved_all.add(r.strip().lower())
    out: List[Finding] = []
    for ch in sorted(state.chapters.values(), key=lambda c: c.number):
        if ch.number > cur:
            continue
        gap = cur - ch.number
        if gap < DORMANT_THREAD_GAP_CHAPTERS:
            continue
        for fs in ch.foreshadowing_planted:
            key = fs.strip().lower()
            if key in resolved_all:
                continue
            # Loose match: any resolved entry contains the planted snippet (or vice versa)
            if any(key in r or r in key for r in resolved_all):
                continue
            out.append(Finding(
                severity="warning",
                category="unresolved_foreshadowing",
                message=f"Foreshadowing planted in ch{ch.number} not yet paid off "
                        f"({gap} chapters later): {fs[:80]}",
                suggestion="Pay it off, hint at it again, or accept and document.",
                chapter=ch.number,
            ))
    return out


def check_absent_characters(state: "StoryState", as_of_chapter: Optional[int] = None) -> List[Finding]:
    cur = as_of_chapter if as_of_chapter is not None else _current_chapter(state)
    if cur == 0:
        return []
    out: List[Finding] = []
    for char in state.characters.values():
        if char.role in ("minor",):
            continue
        if char.last_appearance_chapter == 0:
            # Never seen — flag only if they're a main role
            if char.role in ("protagonist", "antagonist"):
                out.append(Finding(
                    severity="warning",
                    category="never_appeared",
                    message=f"{char.full_name} ({char.role}) has not appeared in any chapter yet.",
                    suggestion="Introduce them or downgrade role.",
                    entity_id=char.id,
                ))
            continue
        gap = cur - char.last_appearance_chapter
        if gap > ABSENT_CHARACTER_GAP_CHAPTERS:
            out.append(Finding(
                severity="warning",
                category="absent_character",
                message=f"{char.full_name} ({char.role}) hasn't appeared in {gap} chapters "
                        f"(last: ch{char.last_appearance_chapter}).",
                suggestion="Reintroduce, reference, or document the absence.",
                chapter=cur,
                entity_id=char.id,
            ))
    return out


def check_dead_characters_reappearing(state: "StoryState") -> List[Finding]:
    out: List[Finding] = []
    for char in state.characters.values():
        es = (char.emotional_state or "").lower()
        notes = (char.notes or "").lower()
        died_marker = any(k in es or k in notes for k in DEAD_KEYWORDS)
        if not died_marker:
            continue
        # If they have any later location update or "appears", flag.
        # We can't know the death chapter precisely; conservative: warn if last_appearance > 0.
        out.append(Finding(
            severity="warning",
            category="dead_character_state",
            message=f"{char.full_name} is flagged as dead/killed but state still tracks them "
                    f"as active (last ch{char.last_appearance_chapter}).",
            suggestion="If resurrection/flashback is intentional, document it; otherwise set role=minor and freeze state.",
            entity_id=char.id,
        ))
    return out


def check_chapter_file_consistency(state: "StoryState", project_path: Path) -> List[Finding]:
    """Mismatches between chapter.status and what files exist on disk."""
    out: List[Finding] = []
    manuscript = project_path / "outputs" / "manuscript"
    for ch in state.chapters.values():
        draft = manuscript / f"chapter_{ch.number:03d}_draft.md"
        revised = manuscript / f"chapter_{ch.number:03d}_revised.md"
        has_draft = draft.exists()
        has_revised = revised.exists()
        if ch.status in ("complete", "validated", "edited") and not (has_draft or has_revised):
            out.append(Finding(
                severity="critical",
                category="missing_chapter_file",
                message=f"Chapter {ch.number} status is '{ch.status}' but no draft/revised file exists.",
                suggestion="Re-run write/edit, or correct the status field.",
                chapter=ch.number,
            ))
        if ch.status == "planned" and has_draft:
            out.append(Finding(
                severity="info",
                category="status_drift",
                message=f"Chapter {ch.number} has a draft file but status is still 'planned'.",
                suggestion="Bump status to 'drafted' (re-submit via `write --draft-file`).",
                chapter=ch.number,
            ))
    return out


def check_required_character_fields(state: "StoryState") -> List[Finding]:
    out: List[Finding] = []
    for char in state.characters.values():
        if char.role in ("protagonist", "antagonist") and not char.internal_desire:
            out.append(Finding(
                severity="info",
                category="thin_character",
                message=f"{char.full_name} ({char.role}) has no internal_desire set.",
                suggestion="A protagonist/antagonist without an internal desire is fragile.",
                entity_id=char.id,
            ))
    return out


# --------------------------------------------------------------------- runners

ALL_CHECKS = (
    check_dormant_threads,
    check_overdue_threads,
    check_unresolved_foreshadowing,
    check_absent_characters,
    check_dead_characters_reappearing,
    check_required_character_fields,
)


def run_all(state: "StoryState", project_path: Optional[Path] = None,
            as_of_chapter: Optional[int] = None) -> List[Finding]:
    """Run every check that applies. project_path enables file-consistency checks."""
    out: List[Finding] = []
    for check in ALL_CHECKS:
        # check_* functions that take only `state` won't accept as_of_chapter — handle both
        try:
            out.extend(check(state, as_of_chapter))  # type: ignore[arg-type]
        except TypeError:
            out.extend(check(state))  # type: ignore[arg-type]
    if project_path is not None:
        out.extend(check_chapter_file_consistency(state, project_path))
    return out


def summarize(findings: List[Finding]) -> str:
    if not findings:
        return "✅ continuity engine: no findings."
    by_severity = {"critical": [], "warning": [], "info": []}
    for f in findings:
        by_severity.setdefault(f.severity, []).append(f)
    lines = [
        f"continuity engine: {len(findings)} finding(s) "
        f"({len(by_severity['critical'])} critical, "
        f"{len(by_severity['warning'])} warning, "
        f"{len(by_severity['info'])} info)\n"
    ]
    for sev in ("critical", "warning", "info"):
        for f in by_severity.get(sev, []):
            lines.append(f.format())
            lines.append("")
    return "\n".join(lines).rstrip()


def to_context_block(findings: List[Finding]) -> str:
    """Render findings as a context block to inject into the LLM Guardian's prompt."""
    if not findings:
        return "Deterministic pre-check: no automated findings.\n"
    lines = ["Deterministic pre-check findings (verify and incorporate into your report):", ""]
    for f in findings:
        head = f"- [{f.severity.upper()}] {f.category}"
        if f.chapter is not None:
            head += f" ch{f.chapter}"
        lines.append(head + ": " + f.message)
        if f.suggestion:
            lines.append(f"  suggestion: {f.suggestion}")
    return "\n".join(lines) + "\n"
