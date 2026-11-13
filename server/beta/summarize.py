"""The Editor reads unresolved beta feedback and posts themes per chapter to the writers' room."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Optional

from sqlmodel import Session, select

from .. import jobs, llm
from ..agents import context
from ..agents import runtime as rt
from ..db import engine, session_scope
from ..models import Agent, Run
from ..models.beta_extra import BetaComment, BetaReader, BetaRound

SYNC = False  # tests flip this to run inline

TASK_SPEC = (
    "Beta readers left the feedback below on this chapter. Summarize it for the author in 3 to 6 short "
    "bullet points: recurring themes, where readers got confused or bored, what landed. Quote readers "
    "briefly where useful. Do not rewrite the chapter. Respect the Author rulings (binding)."
)


def editor(session: Session, project_id: str) -> Optional[Agent]:
    rt.ensure_cast(session, project_id)
    return session.exec(select(Agent).where(Agent.project_id == project_id, Agent.role == "editor")
                        .order_by(Agent.created_at)).first()


def _feedback(rows: list[tuple[BetaComment, str]]) -> str:
    out = []
    for c, name in rows:
        bits = [f"{name}"]
        if c.reaction != "none":
            bits.append(f"[{c.reaction}]")
        if c.quote:
            bits.append(f'on "{c.quote[:200]}"')
        line = " ".join(bits)
        if c.body:
            line += f": {c.body[:600]}"
        out.append("- " + line)
    return "\n".join(out)


def _work(project_id: str, agent_id: str, round_id: Optional[str]) -> Callable[[str], dict]:
    def fn(run_id: str) -> dict:
        with session_scope() as s:
            agent = s.get(Agent, agent_id)
            q = (select(BetaComment, BetaReader.name).join(BetaReader, BetaReader.id == BetaComment.reader_id)
                 .join(BetaRound, BetaRound.id == BetaComment.round_id)
                 .where(BetaRound.project_id == project_id, BetaComment.resolved == False))  # noqa: E712
            if round_id:
                q = q.where(BetaComment.round_id == round_id)
            by_ch: dict[int, list] = defaultdict(list)
            for c, name in s.exec(q.order_by(BetaComment.chapter, BetaComment.created_at)).all():
                by_ch[c.chapter].append((c, name))
            posted = []
            for n in sorted(by_ch):
                jobs.check(run_id)
                pack = context.build(s, project_id, agent, "edit", n,
                                     instruction="beta reader feedback", task_spec=TASK_SPEC)
                user = pack.user + "\n\n## Beta reader feedback\n" + _feedback(by_ch[n])
                text, route, model = llm.complete(s, pack.system, user, agent=agent)
                run = s.get(Run, run_id)
                if run:
                    run.provider = (route.provider if route else "") or "auto"
                    run.model = model or ""
                    s.add(run)
                thread = rt.chapter_thread(s, project_id, n)
                rt.post(s, project_id, thread.id, f"agent:{agent.id}",
                        f"Beta reader feedback, chapter {n} ({len(by_ch[n])} notes):\n\n{text.strip()}",
                        run_id=run_id)
                posted.append(n)
        return {"chapters": posted}
    return fn


def submit(project_id: str, round_id: Optional[str] = None) -> Run:
    with Session(engine()) as s:
        agent = editor(s, project_id)
        if agent is None:
            raise ValueError("No Editor agent on this project")
        agent_id = agent.id
    fn = _work(project_id, agent_id, round_id)
    inp = {"round_id": round_id}
    if not SYNC:
        return jobs.submit(project_id, "beta_summary", fn, agent_id=agent_id, input=inp)
    with Session(engine()) as s:
        run = Run(project_id=project_id, agent_id=agent_id, task="beta_summary", input=inp)
        s.add(run)
        s.commit()
        s.refresh(run)
        s.expunge(run)
    jobs._execute(run.id, project_id, fn)  # noqa: SLF001 - inline mode for tests
    return run
