"""Codex auto-extraction: propose entries for names the chapters use but the Codex lacks.

    run = propose(project_id, chapter=None)

Two passes: a cheap deterministic scan (core.codex_extract) finds recurring proper
nouns that aren't in the Codex, aren't already proposed and weren't dismissed;
then ONE model call (the Architect) classifies them and drops non-entities.
Results are CodexProposal rows (status=open) the author accepts or dismisses.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from sqlmodel import Session, select

from core.codex_extract import extract_proposals

from .. import events, jobs, llm
from ..db import engine, session_scope
from ..models import Agent, Chapter, CodexEntry, Run
from ..models.codex_extra import CodexProposal
from . import context

SYNC = False  # tests flip this to run jobs inline
KINDS = ("character", "location", "item", "lore", "faction", "event")
MAX_CANDIDATES = 40
MAX_EVIDENCE = 200
STOPWORDS = {
    "the", "a", "an", "and", "but", "or", "he", "she", "they", "it", "we", "i", "you", "his", "her", "their",
    "chapter", "part", "act", "mr", "mrs", "ms", "dr", "sir", "lord", "lady", "god", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december", "english", "yes", "no", "oh",
}
_KIND_MAP = {"worldbuilding": "lore", "location": "location", "character": "character", "item": "item"}

TASK_SPEC = (
    "You are reviewing candidate names found in the manuscript that are not yet in the Codex. For each "
    "candidate that is a real story entity, classify it. Drop anything that is not an entity (common words, "
    "exclamations, sentence-initial words, real-world generic terms). Reply with STRICT JSON only: an array of "
    '{"name": str, "kind": str, "summary": str, "first_chapter": int, "evidence_quote": str}. '
    f"`kind` is one of: {', '.join(KINDS)}. `summary` is one or two sentences of what the text establishes, "
    f"no speculation. `evidence_quote` is copied VERBATIM from the chapter text, at most {MAX_EVIDENCE} "
    "characters. Use only names from the candidate list. Return [] if none are entities."
)


def norm(name: str) -> str:
    return " ".join((name or "").lower().split())


def architect(session: Session, project_id: str) -> Optional[Agent]:
    try:
        from .runtime import ensure_cast
        ensure_cast(session, project_id)
    except ImportError:  # pragma: no cover
        pass
    for role in ("architect", "guardian"):
        a = session.exec(select(Agent).where(Agent.project_id == project_id, Agent.role == role)
                         .order_by(Agent.created_at)).first()
        if a:
            return a
    return None


def known_names(session: Session, project_id: str) -> set[str]:
    """Codex names + aliases, and every name already proposed (open, accepted or dismissed)."""
    names: set[str] = set()
    for e in session.exec(select(CodexEntry).where(CodexEntry.project_id == project_id)).all():
        names.add(norm(e.name))
        names.update(norm(a) for a in (e.aliases or []) if isinstance(a, str))
    for n in session.exec(select(CodexProposal.name).where(CodexProposal.project_id == project_id)).all():
        names.add(norm(n))
    names.discard("")
    return names


def chapters_text(session: Session, project_id: str, chapter: Optional[int] = None) -> dict[int, str]:
    q = select(Chapter).where(Chapter.project_id == project_id)
    if chapter is not None:
        q = q.where(Chapter.number == chapter)
    return {c.number: c.text for c in session.exec(q.order_by(Chapter.number)).all() if c.text.strip()}


def candidates(session: Session, project_id: str, chapter: Optional[int] = None) -> list[dict]:
    """Deterministic pass: recurring capitalised names not already known."""
    texts = chapters_text(session, project_id, chapter)
    known = known_names(session, project_id)
    raw: list[dict] = []
    # Join compounds ("Marsh and Cole") BEFORE filtering known/dismissed names,
    # so a dismissed fragment like "Cole" can't block the real entity.
    for p in extract_proposals(texts, known_names=set(), min_mentions=2, limit=MAX_CANDIDATES * 4):
        if norm(p.name) in STOPWORDS:
            continue
        raw.append({"name": p.name, "kind": _KIND_MAP.get(p.entry_type, "lore"), "mentions": p.mentions,
                    "first_chapter": p.chapters[0] if p.chapters else None, "excerpt": p.excerpt})
    out = [c for c in join_compound_names(raw, texts) if norm(c["name"]) not in known]
    return out[:MAX_CANDIDATES]


def join_compound_names(cands: list[dict], texts: dict[int, str]) -> list[dict]:
    """'Marsh and Cole' is one firm, not two factions. When two candidates almost
    always appear as 'A and B' (or 'A & B'), propose the compound name instead."""
    corpus = "\n".join(texts.values())
    by_name = {c["name"]: c for c in cands}
    merged: set[str] = set()
    out: list[dict] = []
    for a in cands:
        if a["name"] in merged:
            continue
        for b in cands:
            if b is a or b["name"] in merged:
                continue
            for joiner in (" and ", " & "):
                compound = f"{a['name']}{joiner}{b['name']}"
                together = corpus.count(compound)
                alone_a = len(re.findall(rf"\b{re.escape(a['name'])}\b", corpus))
                alone_b = len(re.findall(rf"\b{re.escape(b['name'])}\b", corpus))
                # Nearly every mention of both names is inside the compound.
                if together and together >= 0.8 * min(alone_a, alone_b):
                    merged.update({a["name"], b["name"]})
                    out.append({**a, "name": compound, "mentions": together,
                                "kind": a["kind"] if a["kind"] == b["kind"] else "faction"})
                    break
            if a["name"] in merged:
                break
        if a["name"] not in merged:
            out.append(a)
    return [c for c in out if c["name"] not in merged or c["name"] not in by_name]


def parse(raw: str) -> list[dict]:
    m = re.search(r"\[.*\]", raw or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def validate(items: list[dict], cands: list[dict], texts: dict[int, str]) -> list[dict]:
    by_name = {norm(c["name"]): c for c in cands}
    full = "\n\n".join(texts[n] for n in sorted(texts))
    out: list[dict] = []
    seen: set[str] = set()
    for d in items:
        key = norm(str(d.get("name") or ""))
        cand = by_name.get(key)
        if not cand or key in seen:
            continue
        seen.add(key)
        kind = str(d.get("kind") or cand["kind"]).lower()
        quote = str(d.get("evidence_quote") or "").strip()[:MAX_EVIDENCE]
        if not quote or quote not in full:
            quote = cand["excerpt"][:MAX_EVIDENCE] if cand.get("excerpt") and cand["excerpt"][:MAX_EVIDENCE] in full \
                else ""
        try:
            first = int(d.get("first_chapter")) if d.get("first_chapter") is not None else cand["first_chapter"]
        except (TypeError, ValueError):
            first = cand["first_chapter"]
        if first not in texts:
            first = cand["first_chapter"]
        out.append({"name": cand["name"], "kind": kind if kind in KINDS else cand["kind"],
                    "summary": str(d.get("summary") or "")[:600], "first_chapter": first, "evidence": quote})
    return out


def _work(project_id: str, chapter: Optional[int], agent_id: str) -> Callable[[str], dict]:
    def fn(run_id: str) -> dict:
        with session_scope() as s:
            cands = candidates(s, project_id, chapter)
            if not cands:
                return {"candidates": 0, "proposals": 0}
            agent = s.get(Agent, agent_id)
            texts = chapters_text(s, project_id, chapter)
            pack = context.build(s, project_id, agent, "plan", chapter, instruction="Codex extraction",
                                 task_spec=TASK_SPEC)
            listing = "\n".join(
                f"- {c['name']} (seen {c['mentions']}x, first in ch {c['first_chapter']}): “{c['excerpt']}”"
                for c in cands)
            user = f"{pack.user}\n\n## Candidates\n{listing}\n\n## Task\n{TASK_SPEC}"
            raw, route, model = llm.complete(s, pack.system, user, agent=agent)
            run = s.get(Run, run_id)
            if run:
                usage = llm.last_usage()
                run.provider = (route.provider if route else "") or "auto"
                run.model = model or (route.model if route else "") or ""
                run.tokens_in = usage.get("input") or context.est_tokens(pack.system + user)
                run.tokens_out = usage.get("output") or context.est_tokens(raw)
                s.add(run)
            items = validate(parse(raw), cands, texts)
            known = known_names(s, project_id)
            items = [d for d in items if norm(d["name"]) not in known]
            for d in items:
                s.add(CodexProposal(project_id=project_id, **d))
        events.publish(project_id, "codex.updated", {"proposals": len(items)})
        return {"candidates": len(cands), "proposals": len(items)}
    return fn


def propose(project_id: str, chapter: Optional[int] = None) -> Run:
    with Session(engine()) as s:
        agent = architect(s, project_id)
        if agent is None:
            raise ValueError("No Architect agent on this project")
        agent_id = agent.id
    fn = _work(project_id, chapter, agent_id)
    inp = {"chapter": chapter}
    if not SYNC:
        return jobs.submit(project_id, "extract", fn, agent_id=agent_id, chapter=chapter, input=inp)
    with Session(engine()) as s:
        run = Run(project_id=project_id, agent_id=agent_id, task="extract", chapter=chapter, input=inp)
        s.add(run)
        s.commit()
        s.refresh(run)
        s.expunge(run)
    jobs._execute(run.id, project_id, fn)  # noqa: SLF001 - inline mode for tests
    return run
