"""Agent runtime: the cast, tasks, the writers' room and handoffs.

    run_task(project_id, agent_id, task, chapter, instruction) -> Run

Every task runs through jobs.submit (or inline when SYNC is set, for tests).
Work that triggers more work (handoffs, pipeline steps) is queued as
"follow-ups" and started only after the current run's DB session has closed,
so nested runs never fight over a write lock.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from sqlmodel import Session, select

from .. import events, jobs, llm
from ..db import engine, session_scope
from ..models import Agent, Chapter, ChapterVersion, ContinuityExemption, Message, Run, Thread
from ..models.base import now
from ..services.continuity import continuity_findings
from . import context as ctx
from . import memory as mem

TASKS = ("plan", "draft", "revise", "edit", "check", "voice", "chat")
PIPELINE = ("plan", "draft", "edit", "check")
MAX_HOPS = 4
SYNC = False  # tests flip this to run jobs inline

DEFAULT_CAST = [
    ("architect", "Architect", "Plans the book: synopsis, beats, structure and stakes per chapter."),
    ("scribe", "Scribe", "Drafts chapter prose from the beats, in the author's voice."),
    ("editor", "Editor", "Line and structural edits. Tightens prose without flattening voice."),
    ("guardian", "Guardian", "Guards continuity: facts, timeline, who knows what, where everyone is."),
    ("curator", "Curator", "Keeps the voice consistent with the author's Voice DNA."),
    ("researcher", "Researcher", "Looks up real-world facts the story leans on and reports what is uncertain."),
]

HANDOFF_RE = re.compile(r"^\s*HANDOFF\s+@(.+?)\s*:\s*(.+?)\s*$", re.M)
TASK_WORDS = [("revise", "revise"), ("draft", "draft"), ("write", "draft"), ("edit", "edit"), ("tighten", "edit"),
              ("continuity", "check"), ("check", "check"), ("outline", "plan"), ("beats", "plan"), ("plan", "plan"),
              ("voice", "voice"), ("style", "voice")]


# ---- cast -------------------------------------------------------------------------

def ensure_cast(session: Session, project_id: str) -> list[Agent]:
    agents = list(session.exec(select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)).all())
    if agents:
        return agents
    for role, name, brief in DEFAULT_CAST:
        session.add(Agent(project_id=project_id, role=role, name=name, brief=brief,
                          temperature=0.8 if role == "scribe" else 0.5,
                          use_voice_dna=role in ("scribe", "editor", "curator")))
    session.commit()
    return list(session.exec(select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at)).all())


def pick_agent(session: Session, project_id: str, task: str, chapter: Optional[int] = None) -> Optional[Agent]:
    role = ctx.TASK_ROLE.get(task, "scribe")
    agents = [a for a in ensure_cast(session, project_id) if a.enabled]
    if chapter is not None and role == "scribe":
        ch = get_chapter(session, project_id, chapter)
        if ch and ch.assigned_agent_id:
            a = next((x for x in agents if x.id == ch.assigned_agent_id), None)
            if a:
                return a
    return next((a for a in agents if a.role == role), None)


def get_chapter(session: Session, project_id: str, n: int) -> Optional[Chapter]:
    return session.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == n)).first()


# ---- threads & messages -------------------------------------------------------------

def chapter_thread(session: Session, project_id: str, chapter: int) -> Thread:
    t = session.exec(select(Thread).where(Thread.project_id == project_id, Thread.chapter == chapter,
                                          Thread.kind == "room")).first()
    if not t:
        t = Thread(project_id=project_id, chapter=chapter, kind="room", title=f"Chapter {chapter}")
        session.add(t)
        session.commit()
        session.refresh(t)
    return t


def post(session: Session, project_id: str, thread_id: str, sender: str, body: str, *, intent: str = "note",
         recipients: Optional[list] = None, actions: Optional[list] = None, run_id: Optional[str] = None) -> Message:
    m = Message(thread_id=thread_id, sender=sender, body=body, intent=intent, recipients=recipients or [],
                actions=actions or [], run_id=run_id)
    session.add(m)
    t = session.get(Thread, thread_id)
    if t:
        t.updated_at = now()
        session.add(t)
    session.commit()
    session.refresh(m)
    events.publish(project_id, "message.created", {"id": m.id, "thread_id": thread_id, "intent": intent})
    return m


def resolve_mention(agents: list[Agent], after_at: str) -> Optional[Agent]:
    """Longest agent name the text right after '@' starts with; else first-word/role match."""
    low = after_at.lower()
    best = None
    for a in agents:
        n = a.name.lower()
        if low.startswith(n) and (len(low) == len(n) or not low[len(n)].isalnum()):
            if best is None or len(n) > len(best.name):
                best = a
    if best:
        return best
    word = re.match(r"[\w-]+", after_at)
    if not word:
        return None
    w = word.group(0).lower()
    return next((a for a in agents if a.name.split()[0].lower() == w), None) or \
        next((a for a in agents if a.role == w), None)


def parse_mentions(agents: list[Agent], body: str) -> list[Agent]:
    out: list[Agent] = []
    for m in re.finditer(r"(?:^|(?<=\s))@", body):
        a = resolve_mention(agents, body[m.end():])
        if a and a not in out:
            out.append(a)
    return out


def transcript(session: Session, thread_id: str, limit: int = 12) -> str:
    msgs = list(session.exec(select(Message).where(Message.thread_id == thread_id)
                             .order_by(Message.created_at.desc()).limit(limit)).all())[::-1]
    names = {}
    lines = []
    for m in msgs:
        if m.sender.startswith("agent:"):
            aid = m.sender[6:]
            if aid not in names:
                a = session.get(Agent, aid)
                names[aid] = a.name if a else "Agent"
            who = names[aid]
        else:
            who = "Author" if m.sender == "author" else "System"
        lines.append(f"{who}: {m.body[:600]}")
    return "\n".join(lines)


def infer_task(request: str, chapter: Optional[int]) -> str:
    if chapter is None:
        return "chat"
    low = request.lower()
    for word, task in TASK_WORDS:
        if re.search(rf"\b{word}", low):
            return task
    return "chat"


# ---- running ---------------------------------------------------------------------------

def _submit(project_id: str, task: str, fn: Callable[[str], dict], *, agent_id: str, chapter: Optional[int],
            input: dict) -> Run:
    if not SYNC:
        return jobs.submit(project_id, task, fn, agent_id=agent_id, chapter=chapter, input=input)
    with Session(engine()) as s:
        run = Run(project_id=project_id, agent_id=agent_id, task=task, chapter=chapter, input=input)
        s.add(run)
        s.commit()
        s.refresh(run)
        s.expunge(run)
    jobs._execute(run.id, project_id, fn)  # noqa: SLF001 - inline mode for tests
    return run


def run_task(project_id: str, agent_id: str, task: str, chapter: Optional[int] = None, instruction: str = "", *,
             thread_id: Optional[str] = None, hops: int = 0, pipeline: Optional[list] = None) -> Run:
    if task not in TASKS:
        raise ValueError(f"Unknown task {task}")
    payload = {"instruction": instruction, "thread_id": thread_id, "hops": hops, "pipeline": list(pipeline or [])}

    def fn(run_id: str) -> dict:
        followups: list[Callable[[], None]] = []
        with session_scope() as s:
            out = _execute(s, run_id, project_id, agent_id, task, chapter, payload, followups)
        for f in followups:
            f()
        return out

    return _submit(project_id, task, fn, agent_id=agent_id, chapter=chapter, input=payload)


def _complete(s: Session, run_id: str, agent: Agent, system: str, user: str) -> str:
    text, route, model = llm.complete(s, system, user, agent=agent)
    run = s.get(Run, run_id)
    if run:
        run.provider = (route.provider if route else "") or run.provider or "auto"
        run.model = model or (route.model if route else "") or ""
        usage = llm.last_usage()  # real counts when the provider reports them
        run.tokens_in += usage.get("input") or (ctx.est_tokens(system) + ctx.est_tokens(user))
        run.tokens_out += usage.get("output") or ctx.est_tokens(text)
        s.add(run)
        s.commit()
    events.publish(agent.project_id, "run.updated", {"id": run_id, "status": "running"})
    return text or ""


def _version(s: Session, ch: Chapter, kind: str, text: str, agent: Agent, model: str, note: str = "") -> ChapterVersion:
    v = ChapterVersion(chapter_id=ch.id, kind=kind, text=text, word_count=len(text.split()),
                       produced_by=f"agent:{agent.id}", model=model, note=note)
    s.add(v)
    s.commit()
    s.refresh(v)
    return v


def _set_text(s: Session, ch: Chapter, text: str, status: Optional[str] = None) -> None:
    ch.text = text
    ch.word_count = len(text.split())
    if status:
        ch.status = status
    ch.updated_at = now()
    s.add(ch)
    s.commit()
    events.publish(ch.project_id, "chapter.updated", {"number": ch.number})


def _clean_prose(text: str) -> str:
    try:
        from core.prose_sanitize import sanitize_manuscript
        body, _ = sanitize_manuscript(text)
        return body.strip()
    except Exception:  # noqa: BLE001
        return re.sub(r"\[(\w+)\].*?\[/\1\]", "", text, flags=re.S).strip()


def _bullets(text: str) -> list[str]:
    return [ln.strip()[1:].strip() for ln in text.splitlines() if ln.strip().startswith(("-", "*"))
            and ln.strip()[1:].strip()]


def _execute(s: Session, run_id: str, project_id: str, agent_id: str, task: str, chapter: Optional[int],
             payload: dict, followups: list) -> dict:
    agent = s.get(Agent, agent_id)
    if not agent:
        raise ValueError("Agent not found")
    instruction = payload.get("instruction") or ""
    hops = int(payload.get("hops") or 0)
    thread_id = payload.get("thread_id")
    if not thread_id and chapter is not None:
        thread_id = chapter_thread(s, project_id, chapter).id
    ch = get_chapter(s, project_id, chapter) if chapter is not None else None
    if task not in ("chat",) and chapter is not None and not ch:
        raise ValueError(f"Chapter {chapter} not found")
    me = f"agent:{agent.id}"
    out: dict = {}

    def say(body: str, **kw) -> Message | None:
        if not thread_id:
            return None
        return post(s, project_id, thread_id, me, body, run_id=run_id, **kw)

    if task == "chat":
        pack = ctx.build(s, project_id, agent, task, chapter, instruction,
                         transcript=transcript(s, thread_id) if thread_id else "",
                         task_spec=_chat_spec(s, project_id, agent))
        text = _complete(s, run_id, agent, pack.system, pack.user)
        handoffs = HANDOFF_RE.findall(text)
        reply = HANDOFF_RE.sub("", text).strip()
        if reply:
            say(reply, intent="note")
        agents = [a for a in ensure_cast(s, project_id) if a.enabled]
        for name, request in handoffs:
            target = resolve_mention(agents, name)
            if not target or target.id == agent.id:
                continue
            _handoff(s, project_id, thread_id, agent, target, request, chapter, hops, run_id, followups)
        out = {"reply": reply, "handoffs": len(handoffs)}

    elif task == "plan":
        spec = ("Plan this chapter. Reply in exactly this format and nothing else:\n"
                "SYNOPSIS: <two or three sentences>\nBEATS:\n- <beat>\n- <beat>\n(5 to 9 beats)")
        pack = ctx.build(s, project_id, agent, task, chapter, instruction, task_spec=spec)
        text = _complete(s, run_id, agent, pack.system, pack.user)
        syn = re.search(r"SYNOPSIS:\s*(.+?)(?:\n\s*BEATS:|\Z)", text, re.S)
        beats_part = text.split("BEATS:", 1)[1] if "BEATS:" in text else text
        beats = _bullets(beats_part)
        if ch:
            if syn:
                ch.synopsis = syn.group(1).strip()
            if beats:
                ch.beats = beats
            ch.updated_at = now()
            s.add(ch)
            s.commit()
            events.publish(project_id, "chapter.updated", {"number": ch.number})
        say(f"Planned chapter {chapter}: {len(beats)} beats." + (f"\n\n{ch.synopsis}" if ch and ch.synopsis else ""),
            intent="result")
        out = {"synopsis": ch.synopsis if ch else "", "beats": beats}

    elif task == "draft":
        spec = "Write the full chapter prose now, then the [SCRIBE_STATE_UPDATE] block."
        pack = ctx.build(s, project_id, agent, task, chapter, instruction, task_spec=spec)
        raw = _complete(s, run_id, agent, pack.system, pack.user)
        prose = _clean_prose(raw)
        run = s.get(Run, run_id)
        _version(s, ch, "draft", prose, agent, run.model if run else "")
        _set_text(s, ch, prose, status="drafted")
        facts = mem.facts_from_scribe(raw)
        if not facts and prose:
            facts = _bullets(_complete(s, run_id, agent,
                                       "You extract canon facts from fiction. Reply only with a bulleted list.",
                                       "List up to 5 new, specific story facts established in this chapter, "
                                       f"one per line starting with '- '.\n\n{prose[:12000]}"))[:5]
        for f in facts:
            mem.remember(s, project_id, "fact", f, chapter=chapter, source=f"chapter:{chapter}", importance=0.6)
        say(f"Drafted chapter {chapter}: {len(prose.split())} words. Logged {len(facts)} new facts.", intent="result")
        out = {"words": len(prose.split()), "facts": facts}

    elif task in ("edit", "revise"):
        spec = ("Edit this chapter. Return the FULL edited chapter inside [REVISED_CHAPTER] ... [/REVISED_CHAPTER], "
                "then the [EDITOR_STATE_UPDATE] block.") if task == "edit" else \
            ("Revise this chapter to address the note. Return the FULL revised chapter inside "
             "[REVISED_CHAPTER] ... [/REVISED_CHAPTER], then the [EDITOR_STATE_UPDATE] block.")
        pack = ctx.build(s, project_id, agent, task, chapter, instruction, task_spec=spec)
        raw = _complete(s, run_id, agent, pack.system, pack.user)
        m = re.search(r"\[REVISED_CHAPTER\](.*?)\[/REVISED_CHAPTER\]", raw, re.S)
        revised = _clean_prose(m.group(1) if m else raw)
        upd = mem.parse_block_fields(raw, "EDITOR_STATE_UPDATE")
        summary = "; ".join(upd.get("Improvements_Made", [])[:4])
        run = s.get(Run, run_id)
        v = _version(s, ch, "revision" if task == "revise" else "edit", revised, agent, run.model if run else "",
                     note=summary)
        if agent.autonomy == "autopilot":
            _set_text(s, ch, revised, status="revising")
            say(f"Applied my {task} to chapter {chapter}." + (f" {summary}" if summary else ""), intent="result")
            out = {"version_id": v.id, "applied": True}
        else:
            say(f"Proposed {task} for chapter {chapter} ({len(revised.split())} words)."
                + (f"\n\n{summary}" if summary else ""), intent="proposal",
                actions=[{"label": "Accept", "action": "accept", "version_id": v.id},
                         {"label": "Reject", "action": "reject", "version_id": v.id}])
            out = {"version_id": v.id, "applied": False}

    elif task == "check":
        findings = continuity_findings(s, project_id, chapter) or []
        listed = "\n".join(f"- [{f.get('severity', 'warning')}] {f.get('message', '')}" for f in findings[:20])
        spec = ("Check this chapter for continuity problems against the Codex and memories."
                + (f"\nDeterministic checks already found:\n{listed}" if listed else ""))
        pack = ctx.build(s, project_id, agent, task, chapter, instruction, task_spec=spec)
        raw = _complete(s, run_id, agent, pack.system, pack.user)
        rep = mem.parse_block_fields(raw, "CONTINUITY_REPORT")
        status = ((rep.get("Status") or ["PASS"])[0] or "PASS").upper().split()[0]
        issues = rep.get("Critical_Issues", []) + rep.get("Warnings", [])
        for f in mem.parse_block_fields(raw, "CONTINUITY_STATE_UPDATE").get("New_Facts_Established", [])[:6]:
            mem.remember(s, project_id, "fact", f, chapter=chapter, source=f"chapter:{chapter}", importance=0.55)
        all_issues = [f.get("message", "") for f in findings] + issues
        if findings or (status in ("FAIL", "WARNING") and issues):
            body = "Continuity objection on chapter %s:\n" % chapter + "\n".join(f"- {x}" for x in all_issues[:8] if x)
            say(body, intent="objection", actions=[
                {"label": "Fix in text", "action": "fix"},
                {"label": "This is intentional", "action": "intentional",
                 "keys": [f.get("key") for f in findings if f.get("key")]},
            ])
        else:
            say(f"Continuity check on chapter {chapter}: clean.", intent="result")
        out = {"status": "WARNING" if findings and status == "PASS" else status, "findings": len(findings),
               "issues": all_issues}

    elif task == "voice":
        spec = "Assess this chapter's voice against the style guide and end with the [STYLE_STATE_UPDATE] block."
        pack = ctx.build(s, project_id, agent, task, chapter, instruction, task_spec=spec)
        raw = _complete(s, run_id, agent, pack.system, pack.user)
        upd = mem.parse_block_fields(raw, "STYLE_STATE_UPDATE")
        drift = upd.get("Drift_Detected", [])
        for d in drift[:5]:
            mem.remember(s, project_id, "style", d, chapter=chapter, source=f"chapter:{chapter}", importance=0.5)
        score = (upd.get("Consistency_Score") or [""])[0]
        say(f"Voice check on chapter {chapter}" + (f": consistency {score}" if score else "") +
            (f". {len(drift)} drift notes." if drift else "."), intent="result")
        out = {"consistency": score, "drift": drift}
    else:
        pack = None

    meta = pack.meta() if pack else {}
    out["context"] = meta
    run = s.get(Run, run_id)
    if run:
        run.output = {**(run.output or {}), "context": meta}
        s.add(run)
        s.commit()

    summary = out.get("reply") or ""
    mem.remember(s, project_id, "episode",
                 f"{agent.name} ran {task}" + (f" on chapter {chapter}" if chapter is not None else "")
                 + (f": {summary[:160]}" if summary else "") + (f" (note: {instruction[:120]})" if instruction else ""),
                 agent_id=agent.id, chapter=chapter, source=f"run:{run_id}", importance=0.3)

    remaining = list(payload.get("pipeline") or [])
    if remaining and chapter is not None:
        nxt_task = remaining[0]
        nxt = pick_agent(s, project_id, nxt_task, chapter)
        if nxt:
            say(f"{task.capitalize()} is done. Over to {nxt.name} to {nxt_task}.", intent="handoff",
                recipients=[nxt.id])
            pid, nid, tid, rest = project_id, nxt.id, thread_id, remaining[1:]
            followups.append(lambda: run_task(pid, nid, nxt_task, chapter, "", thread_id=tid, pipeline=rest))
    return out


def _chat_spec(s: Session, project_id: str, agent: Agent) -> str:
    team = ", ".join(f"@{a.name} ({a.role})" for a in ensure_cast(s, project_id) if a.enabled and a.id != agent.id)
    return (f"You are {agent.name}, replying in the writers' room. Answer the latest message briefly "
            "(under 150 words), in plain prose, from your role. If a teammate should act, add a separate line "
            "exactly like `HANDOFF @<Name>: <request>`. Only hand off when it is genuinely needed. "
            f"Your teammates: {team}.")


def _handoff(s: Session, project_id: str, thread_id: Optional[str], src: Agent, target: Agent, request: str,
             chapter: Optional[int], hops: int, run_id: str, followups: list) -> None:
    if not thread_id:
        return
    next_hop = hops + 1
    task = infer_task(request, chapter)
    if next_hop > MAX_HOPS:
        post(s, project_id, thread_id, f"agent:{src.id}", request, intent="handoff", recipients=[target.id],
             run_id=run_id)
        post(s, project_id, thread_id, "system",
             f"Handoff chain stopped after {MAX_HOPS} hops. Reply to continue.", intent="note")
        return
    if target.autonomy == "autopilot":
        post(s, project_id, thread_id, f"agent:{src.id}", request, intent="handoff", recipients=[target.id],
             run_id=run_id)
        tgt_id = target.id
        followups.append(lambda: run_task(project_id, tgt_id, task, chapter, request, thread_id=thread_id,
                                          hops=next_hop))
    else:
        post(s, project_id, thread_id, f"agent:{src.id}", request, intent="handoff", recipients=[target.id],
             run_id=run_id, actions=[{"label": "Approve", "action": "run", "hops": next_hop, "task": task},
                                     {"label": "Skip", "action": "dismiss"}])


# ---- author entry points -------------------------------------------------------------------

def author_message(session: Session, project_id: str, thread: Thread, body: str) -> tuple[Message, list[Run]]:
    agents = [a for a in ensure_cast(session, project_id) if a.enabled]
    mentioned = parse_mentions(agents, body)
    msg = post(session, project_id, thread.id, "author", body, intent="question" if mentioned else "note",
               recipients=[a.id for a in mentioned])
    runs = [run_task(project_id, a.id, "chat", thread.chapter, body, thread_id=thread.id, hops=0) for a in mentioned]
    return msg, runs


def execute_action(session: Session, project_id: str, msg: Message, action: str) -> dict:
    """Run a quick-reply action on a message. Returns {"ok", "runs": [...], "note"}."""
    thread = session.get(Thread, msg.thread_id)
    spec = next((a for a in msg.actions or [] if a.get("action") == action), None)
    chapter = thread.chapter if thread else None
    runs: list[Run] = []
    note = ""
    if action == "remember":
        m = mem.remember(session, project_id, "preference", msg.body, chapter=chapter, source=f"message:{msg.id}",
                         importance=0.8)
        return {"ok": True, "runs": [], "memory_id": m.id, "note": "Remembered."}
    if spec is None:
        raise ValueError(f"Action '{action}' is not available on this message")
    ch = get_chapter(session, project_id, chapter) if chapter is not None else None
    if action == "run":
        target_id = (msg.recipients or [None])[0]
        target = session.get(Agent, target_id) if target_id else None
        if not target:
            raise ValueError("Handoff target not found")
        runs.append(run_task(project_id, target.id, spec.get("task") or "chat", chapter, msg.body,
                             thread_id=msg.thread_id, hops=int(spec.get("hops") or 1)))
        note = f"Approved. {target.name} is on it."
    elif action == "dismiss":
        note = "Skipped."
    elif action == "accept":
        v = session.get(ChapterVersion, spec.get("version_id"))
        if not v or not ch:
            raise ValueError("Version not found")
        _set_text(session, ch, v.text, status="revising")
        note = "Accepted. The chapter text now uses this revision."
    elif action == "reject":
        note = "Rejected. The revision stays in version history."
    elif action == "intentional":
        for key in spec.get("keys") or []:
            session.add(ContinuityExemption(project_id=project_id, finding_key=key, reason="Author: intentional"))
        mem.remember(session, project_id, "decision", f"Intentional, not a continuity error: {msg.body[:400]}",
                     chapter=chapter, source=f"message:{msg.id}", importance=0.8, commit=False)
        session.commit()
        note = "Marked intentional. The Guardian will remember."
    elif action == "fix":
        editor = pick_agent(session, project_id, "revise", chapter)
        if not editor or chapter is None:
            raise ValueError("No editor available")
        runs.append(run_task(project_id, editor.id, "revise", chapter, f"Fix this continuity problem:\n{msg.body}",
                             thread_id=msg.thread_id))
        note = f"{editor.name} is revising to fix it."
    msg = session.get(Message, msg.id)
    msg.actions = []
    session.add(msg)
    session.commit()
    if thread and note:
        post(session, project_id, thread.id, "system", note, intent="note")
    return {"ok": True, "runs": [r.id for r in runs], "note": note}


def start_pipeline(session: Session, project_id: str, chapter: int, steps: Optional[list] = None) -> Run:
    steps = [t for t in (steps or PIPELINE) if t in TASKS]
    first = pick_agent(session, project_id, steps[0], chapter)
    if not first:
        raise ValueError(f"No enabled agent for {steps[0]}")
    t = chapter_thread(session, project_id, chapter)
    post(session, project_id, t.id, "system", f"Pipeline started: {' → '.join(steps)}.", intent="note")
    return run_task(project_id, first.id, steps[0], chapter, "", thread_id=t.id, pipeline=steps[1:])
