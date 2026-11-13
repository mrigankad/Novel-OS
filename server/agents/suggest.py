"""Editor line suggestions: track-changes style edits on a chapter.

    run = suggest(project_id, chapter, focus="tighten dialogue")

The job stores Suggestion rows (status=open). It never touches the chapter text;
the author accepts or dismisses each one.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from sqlmodel import Session, select

from .. import events, jobs, llm
from ..db import engine, session_scope
from ..models import Agent, Chapter, Run
from ..models.suggest_extra import Suggestion
from . import context

SYNC = False  # tests flip this to run jobs inline
MAX_SUGGESTIONS = 12
KINDS = ("tighten", "clarity", "voice", "continuity", "grammar")

TASK_SPEC = (
    f"Propose at most {MAX_SUGGESTIONS} line-level edits to the current chapter text. Reply with STRICT JSON "
    'only: an array of objects {"quote": str, "replacement": str, "reason": str, "kind": str}. '
    "`quote` must be copied VERBATIM from the chapter text (exact characters and punctuation), 3 to 60 words, "
    "within a single paragraph. `replacement` is the improved text for that span. `reason` is one short "
    f"sentence. `kind` is one of: {', '.join(KINDS)}. Follow the Author rulings (binding) and the Voice DNA "
    "style guide: never suggest changing anything the author has ruled on. Return [] if nothing needs changing."
)


def editor_agent(session: Session, project_id: str) -> Optional[Agent]:
    try:
        from .runtime import ensure_cast
        ensure_cast(session, project_id)
    except ImportError:  # pragma: no cover - runtime is optional for this module
        pass
    return session.exec(select(Agent).where(Agent.project_id == project_id, Agent.role == "editor")
                        .order_by(Agent.created_at)).first()


def parse(raw: str) -> list[dict]:
    """Pull the JSON array out of a model reply (tolerates code fences and chatter)."""
    m = re.search(r"\[.*\]", raw or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def validate(items: list[dict], text: str) -> list[dict]:
    """Keep exact-substring quotes of 3-60 words; drop no-ops and overlapping spans."""
    out: list[dict] = []
    spans: list[tuple[int, int]] = []
    for d in items:
        quote = str(d.get("quote") or "")
        repl = str(d.get("replacement") or "")
        if not quote.strip() or quote == repl:
            continue
        if not 3 <= len(quote.split()) <= 60:
            continue
        start = text.find(quote)
        if start < 0:
            continue
        end = start + len(quote)
        if any(start < e and s < end for s, e in spans):
            continue
        kind = str(d.get("kind") or "clarity").lower()
        spans.append((start, end))
        out.append({"quote": quote, "replacement": repl, "reason": str(d.get("reason") or "")[:500],
                    "kind": kind if kind in KINDS else "clarity"})
        if len(out) >= MAX_SUGGESTIONS:
            break
    return out


def _work(project_id: str, chapter: int, agent_id: str, focus: str) -> Callable[[str], dict]:
    def fn(run_id: str) -> dict:
        with session_scope() as s:
            agent = s.get(Agent, agent_id)
            ch = s.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == chapter)).first()
            if not ch or not ch.text.strip():
                return {"suggestions": 0}
            pack = context.build(s, project_id, agent, "edit", chapter, instruction=focus, task_spec=TASK_SPEC)
            raw, route, model = llm.complete(s, pack.system, pack.user, agent=agent)
            run = s.get(Run, run_id)
            if run:  # same accounting as other agent runs: real usage, estimate as fallback
                usage = llm.last_usage()
                run.provider = (route.provider if route else "") or "auto"
                run.model = model or (route.model if route else "") or ""
                run.tokens_in = usage.get("input") or context.est_tokens(pack.system + pack.user)
                run.tokens_out = usage.get("output") or context.est_tokens(raw)
                s.add(run)
            items = validate(parse(raw), ch.text)
            # A fresh pass replaces the previous open set for this chapter.
            for old in s.exec(select(Suggestion).where(Suggestion.project_id == project_id,
                                                       Suggestion.chapter == chapter,
                                                       Suggestion.status == "open")).all():
                s.delete(old)
            for d in items:
                s.add(Suggestion(project_id=project_id, chapter=chapter, run_id=run_id, **d))
        events.publish(project_id, "chapter.updated", {"number": chapter, "suggestions": len(items)})
        return {"suggestions": len(items)}
    return fn


def suggest(project_id: str, chapter: int, focus: str = "") -> Run:
    with Session(engine()) as s:
        agent = editor_agent(s, project_id)
        if agent is None:
            raise ValueError("No Editor agent on this project")
        agent_id = agent.id
    fn = _work(project_id, chapter, agent_id, focus)
    inp = {"focus": focus}
    if not SYNC:
        return jobs.submit(project_id, "suggest", fn, agent_id=agent_id, chapter=chapter, input=inp)
    with Session(engine()) as s:
        run = Run(project_id=project_id, agent_id=agent_id, task="suggest", chapter=chapter, input=inp)
        s.add(run)
        s.commit()
        s.refresh(run)
        s.expunge(run)
    jobs._execute(run.id, project_id, fn)  # noqa: SLF001 - inline mode for tests
    return run
