"""Continuity checks over the database. Owner: manuscript area.

Other areas call continuity_findings(); the Guardian agent and the MCP server use it.
Ported from core/continuity_engine.py, but reading DB rows instead of the JSON StoryState.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlmodel import Session, select

from ..models import Chapter, CodexEntry, ContinuityExemption, PlotThread

DORMANT_THREAD_GAP_CHAPTERS = 3
ABSENT_CHARACTER_GAP_CHAPTERS = 5
DEAD_WORDS = {"dead", "killed", "deceased", "died"}
GONE_WORDS = {"lost", "destroyed", "gone", "missing", "sold"}
_EVENT_CHAPTER_FACTS = ("died_chapter", "death_chapter", "lost_chapter", "destroyed_chapter",
                        "status_chapter", "since_chapter")
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _finding(key: str, severity: str, kind: str, message: str, *, chapter: Optional[int] = None,
             entity: Optional[str] = None, suggestion: str = "", fix: Optional[dict] = None) -> dict:
    return {"key": key, "severity": severity, "kind": kind, "message": message, "chapter": chapter,
            "entity": entity, "suggestion": suggestion, "fix": fix}


def _names(e: CodexEntry) -> list[str]:
    names = [e.name] + [a for a in (e.aliases or []) if isinstance(a, str)]
    if e.kind == "character" and " " in e.name.strip():
        names.append(e.name.split()[0])  # "Iris Vale" is usually just "Iris" in prose
    return [n.strip() for n in names if n and len(n.strip()) >= 3]


def _pattern(e: CodexEntry) -> re.Pattern:
    alts = sorted({re.escape(n) for n in _names(e)}, key=len, reverse=True)
    return re.compile(r"(?<![\w])(" + "|".join(alts) + r")(?![\w])", re.IGNORECASE)


def _int(v) -> Optional[int]:
    try:
        return int(str(v).strip().lstrip("ch").strip())
    except (TypeError, ValueError):
        return None


def all_findings(session: Session, project_id: str, as_of: Optional[int] = None) -> list[dict]:
    chapters = session.exec(select(Chapter).where(Chapter.project_id == project_id)
                            .order_by(Chapter.number)).all()
    entries = session.exec(select(CodexEntry).where(CodexEntry.project_id == project_id)).all()
    threads = session.exec(select(PlotThread).where(PlotThread.project_id == project_id)).all()

    written = [c for c in chapters if c.word_count > 0]
    cur = as_of if as_of is not None else (max((c.number for c in written), default=0))
    in_scope = [c for c in written if c.number <= cur]
    out: list[dict] = []

    # Which entries are named in which written chapters.
    appearances: dict[str, list[int]] = {}
    for e in entries:
        if not _names(e):
            continue
        pat = _pattern(e)
        appearances[e.id] = [c.number for c in in_scope if pat.search(c.text)]

    # Plot threads ------------------------------------------------------------
    for t in threads:
        if t.status != "open" or cur == 0:
            continue
        last = t.last_advanced_chapter or t.planted_chapter or 0
        gap = cur - last
        if gap > DORMANT_THREAD_GAP_CHAPTERS:
            out.append(_finding(f"dormant_thread:{t.id}", "warning", "dormant_thread",
                                f"Plot thread '{t.name}' hasn't advanced in {gap} chapters (last touched ch {last}).",
                                chapter=cur, entity=t.id, fix={"type": "chapter", "chapter": cur},
                                suggestion="Touch this thread in the next chapter, or mark it resolved or dropped."))
        if t.target_chapter and cur > t.target_chapter:
            out.append(_finding(f"overdue_thread:{t.id}", "critical", "overdue_thread",
                                f"Plot thread '{t.name}' was due to resolve by ch {t.target_chapter} and is still open at ch {cur}.",
                                chapter=cur, entity=t.id, fix={"type": "chapter", "chapter": cur},
                                suggestion="Resolve it, drop it, or move its target chapter."))

    # Characters --------------------------------------------------------------
    for e in entries:
        if e.kind != "character":
            continue
        seen = appearances.get(e.id, [])
        role = (e.role or "").lower()
        facts = e.facts or {}
        if cur > 0 and role in ("protagonist", "antagonist") and not seen:
            out.append(_finding(f"never_appeared:{e.id}", "warning", "never_appeared",
                                f"{e.name} ({role}) hasn't appeared in any written chapter yet.",
                                entity=e.id, fix={"type": "codex", "id": e.id},
                                suggestion="Introduce them, or change their role."))
        elif seen and role not in ("minor", "") and cur - seen[-1] > ABSENT_CHARACTER_GAP_CHAPTERS:
            out.append(_finding(f"absent_character:{e.id}", "warning", "absent_character",
                                f"{e.name} hasn't appeared in {cur - seen[-1]} chapters (last: ch {seen[-1]}).",
                                chapter=cur, entity=e.id, fix={"type": "chapter", "chapter": cur},
                                suggestion="Reintroduce or reference them, or note the absence."))
        if role in ("protagonist", "antagonist") and not (facts.get("desire") or facts.get("internal_desire")):
            out.append(_finding(f"thin_character:{e.id}", "info", "thin_character",
                                f"{e.name} ({role}) has no desire recorded in the Codex.",
                                entity=e.id, fix={"type": "codex", "id": e.id},
                                suggestion="Add a 'desire' fact: what do they want that they can't say?"))

    # Codex facts contradicted by text (dead characters acting, lost items reappearing) ---
    for e in entries:
        facts = e.facts or {}
        status = str(facts.get("status", "")).strip().lower()
        if status not in DEAD_WORDS and status not in GONE_WORDS:
            continue
        since = next((_int(facts[k]) for k in _EVENT_CHAPTER_FACTS if k in facts and _int(facts[k])), None)
        seen = appearances.get(e.id, [])
        label = "dead" if status in DEAD_WORDS else status
        if since is not None:
            later = [n for n in seen if n > since]
            if later:
                first = later[0]
                kind = "dead_character_activity" if (e.kind == "character" and status in DEAD_WORDS) else "fact_contradiction"
                chs = ", ".join(f"ch {n}" for n in later)
                out.append(_finding(f"{kind}:{e.id}:status", "critical", kind,
                                    f"{e.name} is {label} since ch {since} (Codex), but appears in {chs}.",
                                    chapter=first, entity=e.id, fix={"type": "chapter", "chapter": first},
                                    suggestion="Cut the reference, make it a memory or flashback, or update the Codex."))
        elif e.kind == "character" and status in DEAD_WORDS and seen:
            out.append(_finding(f"dead_character_state:{e.id}", "warning", "dead_character_state",
                                f"{e.name} is marked {label} but still appears in the text (last ch {seen[-1]}).",
                                chapter=seen[-1], entity=e.id, fix={"type": "codex", "id": e.id},
                                suggestion="Add a 'died_chapter' fact so later appearances can be checked."))

    # Chapter status vs text --------------------------------------------------
    for c in chapters:
        if c.status == "planned" and c.word_count > 0:
            out.append(_finding(f"status_drift:{c.id}", "info", "status_drift",
                                f"Chapter {c.number} has {c.word_count} words but is still marked planned.",
                                chapter=c.number, fix={"type": "chapter", "chapter": c.number},
                                suggestion="Mark it drafting or drafted."))
        elif c.status in ("drafted", "revising", "final") and c.word_count == 0:
            out.append(_finding(f"missing_text:{c.id}", "critical", "missing_text",
                                f"Chapter {c.number} is marked {c.status} but has no text.",
                                chapter=c.number, fix={"type": "chapter", "chapter": c.number},
                                suggestion="Write or restore the chapter, or correct its status."))

    out.sort(key=lambda f: (_SEVERITY_ORDER.get(f["severity"], 9), f["chapter"] or 0))
    return out


def exempt_keys(session: Session, project_id: str) -> set[str]:
    return set(session.exec(select(ContinuityExemption.finding_key)
                            .where(ContinuityExemption.project_id == project_id)).all())


def continuity_findings(session: Session, project_id: str, chapter: Optional[int] = None) -> list[dict]:
    """Deterministic findings: [{"key", "severity": critical|warning|info, "kind", "message",
    "chapter", "entity"}], with author exemptions already removed.

    With `chapter`, checks run as of that chapter and only findings about it (or
    book-wide ones with no chapter) are returned.
    """
    found = all_findings(session, project_id, as_of=chapter)
    skip = exempt_keys(session, project_id)
    found = [f for f in found if f["key"] not in skip]
    if chapter is not None:
        found = [f for f in found if f["chapter"] in (chapter, None)]
    return found
