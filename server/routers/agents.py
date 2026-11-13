"""The cast: agents, chapter assignment, runs, tasks and the chapter pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import events
from ..agents import runtime
from ..db import get_session
from ..llm import resolve
from ..models import Agent, Chapter, Message, Project, Run, Thread

router = APIRouter(tags=["agents"])

Autonomy = Literal["ask", "autopilot"]


class AgentIn(BaseModel):
    role: str = "custom"
    name: str
    brief: str = ""
    provider: str = ""
    model: str = ""
    temperature: float = 0.7
    use_voice_dna: bool = True
    autonomy: Autonomy = "ask"
    enabled: bool = True


class AgentPatch(BaseModel):
    name: Optional[str] = None
    brief: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    use_voice_dna: Optional[bool] = None
    autonomy: Optional[Autonomy] = None
    enabled: Optional[bool] = None


class AgentOut(BaseModel):
    id: str
    role: str
    name: str
    brief: str
    provider: str
    model: str
    model_line: str
    temperature: float
    use_voice_dna: bool
    autonomy: str
    enabled: bool
    status: str  # idle | writing | objection
    chapters: list[int]


class RunOut(BaseModel):
    id: str
    agent_id: Optional[str]
    task: str
    chapter: Optional[int]
    status: str
    error: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    output: dict
    created_at: str
    finished_at: Optional[str]


class TaskIn(BaseModel):
    task: str
    chapter: Optional[int] = None
    instruction: str = ""


class AssigneeIn(BaseModel):
    agent_id: Optional[str] = None


class AutonomyIn(BaseModel):
    autonomy: Autonomy


class PipelineIn(BaseModel):
    steps: Optional[list[str]] = None


def _project(s: Session, pid: str) -> Project:
    p = s.get(Project, pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def _agent(s: Session, pid: str, aid: str) -> Agent:
    a = s.get(Agent, aid)
    if not a or a.project_id != pid:
        raise HTTPException(404, "Agent not found")
    return a


def _chapter(s: Session, pid: str, n: int) -> Chapter:
    ch = runtime.get_chapter(s, pid, n)
    if not ch:
        raise HTTPException(404, "Chapter not found")
    return ch


def run_out(r: Run) -> RunOut:
    return RunOut(id=r.id, agent_id=r.agent_id, task=r.task, chapter=r.chapter, status=r.status, error=r.error,
                  provider=r.provider, model=r.model, tokens_in=r.tokens_in, tokens_out=r.tokens_out,
                  output=r.output or {}, created_at=r.created_at.isoformat(),
                  finished_at=r.finished_at.isoformat() if r.finished_at else None)


def _model_line(s: Session, a: Agent) -> str:
    if a.provider or a.model:
        return " · ".join(x for x in [a.provider, a.model] if x)
    route = resolve(s, None)
    if route:
        return "Studio default · " + " · ".join(x for x in [route.provider, route.model] if x)
    return "Studio default"


def _outs(s: Session, pid: str, agents: list[Agent]) -> list[AgentOut]:
    chapters: dict[str, list[int]] = {}
    for aid, n in s.exec(select(Chapter.assigned_agent_id, Chapter.number)
                         .where(Chapter.project_id == pid, Chapter.assigned_agent_id != None)  # noqa: E711
                         .order_by(Chapter.number)).all():
        chapters.setdefault(aid, []).append(n)
    busy = set(s.exec(select(Run.agent_id).where(Run.project_id == pid, Run.status.in_(("queued", "running")))).all())
    objecting: set[str] = set()
    threads = [t.id for t in s.exec(select(Thread).where(Thread.project_id == pid)).all()]
    if threads:
        for m in s.exec(select(Message).where(Message.thread_id.in_(threads), Message.intent == "objection")).all():
            if m.actions and m.sender.startswith("agent:"):
                objecting.add(m.sender[6:])
    line_cache: dict[str, str] = {}
    out = []
    for a in agents:
        key = f"{a.provider}|{a.model}"
        if key not in line_cache:
            line_cache[key] = _model_line(s, a)
        status = "writing" if a.id in busy else "objection" if a.id in objecting else "idle"
        out.append(AgentOut(id=a.id, role=a.role, name=a.name, brief=a.brief, provider=a.provider, model=a.model,
                            model_line=line_cache[key], temperature=a.temperature, use_voice_dna=a.use_voice_dna,
                            autonomy=a.autonomy, enabled=a.enabled, status=status, chapters=chapters.get(a.id, [])))
    return out


@router.get("/projects/{pid}/agents", response_model=list[AgentOut])
def list_agents(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    return _outs(s, pid, runtime.ensure_cast(s, pid))


@router.post("/projects/{pid}/agents", response_model=AgentOut, status_code=201)
def create_agent(pid: str, body: AgentIn, s: Session = Depends(get_session)):
    _project(s, pid)
    runtime.ensure_cast(s, pid)
    a = Agent(project_id=pid, **body.model_dump())
    s.add(a)
    s.commit()
    s.refresh(a)
    return _outs(s, pid, [a])[0]


@router.patch("/projects/{pid}/agents/{aid}", response_model=AgentOut)
def update_agent(pid: str, aid: str, body: AgentPatch, s: Session = Depends(get_session)):
    a = _agent(s, pid, aid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    s.add(a)
    s.commit()
    s.refresh(a)
    return _outs(s, pid, [a])[0]


@router.delete("/projects/{pid}/agents/{aid}", status_code=204)
def delete_agent(pid: str, aid: str, s: Session = Depends(get_session)):
    a = _agent(s, pid, aid)
    for ch in s.exec(select(Chapter).where(Chapter.assigned_agent_id == aid)).all():
        ch.assigned_agent_id = None
        s.add(ch)
    s.delete(a)
    s.commit()


@router.put("/projects/{pid}/agents-autonomy", response_model=list[AgentOut])
def set_autonomy(pid: str, body: AutonomyIn, s: Session = Depends(get_session)):
    """The room's 'Ask before acting / Autopilot' switch: applies to the whole cast."""
    agents = runtime.ensure_cast(s, pid)
    for a in agents:
        a.autonomy = body.autonomy
        s.add(a)
    s.commit()
    return _outs(s, pid, agents)


@router.put("/projects/{pid}/chapters/{n}/assignee")
def set_assignee(pid: str, n: int, body: AssigneeIn, s: Session = Depends(get_session)):
    ch = _chapter(s, pid, n)
    if body.agent_id:
        _agent(s, pid, body.agent_id)
    ch.assigned_agent_id = body.agent_id
    s.add(ch)
    s.commit()
    events.publish(pid, "chapter.updated", {"number": n})
    events.publish(pid, "agent.updated", {"id": body.agent_id})
    return {"number": n, "assigned_agent_id": ch.assigned_agent_id}


@router.post("/projects/{pid}/agents/{aid}/run", response_model=RunOut, status_code=202)
def start_task(pid: str, aid: str, body: TaskIn, s: Session = Depends(get_session)):
    a = _agent(s, pid, aid)
    if body.task not in runtime.TASKS:
        raise HTTPException(422, f"task must be one of {', '.join(runtime.TASKS)}")
    if body.chapter is not None:
        _chapter(s, pid, body.chapter)
    return run_out(runtime.run_task(pid, a.id, body.task, body.chapter, body.instruction))


@router.post("/projects/{pid}/chapters/{n}/tasks/{task}", response_model=RunOut, status_code=202)
def start_chapter_task(pid: str, n: int, task: str, body: Optional[TaskIn] = None, s: Session = Depends(get_session)):
    """Plan / Draft / Edit / Check buttons: the right agent for the chapter picks it up."""
    _chapter(s, pid, n)
    if task not in runtime.TASKS:
        raise HTTPException(422, "Unknown task")
    a = runtime.pick_agent(s, pid, task, n)
    if not a:
        raise HTTPException(409, f"No enabled agent can {task}")
    return run_out(runtime.run_task(pid, a.id, task, n, body.instruction if body else ""))


@router.post("/projects/{pid}/chapters/{n}/pipeline", response_model=RunOut, status_code=202)
def pipeline(pid: str, n: int, body: Optional[PipelineIn] = None, s: Session = Depends(get_session)):
    _chapter(s, pid, n)
    try:
        return run_out(runtime.start_pipeline(s, pid, n, body.steps if body else None))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/projects/{pid}/room/chapters")
def room_chapters(pid: str, s: Session = Depends(get_session)):
    """Light chapter list for the room's chapter switcher (read-only view of the manuscript)."""
    _project(s, pid)
    rows = s.exec(select(Chapter.number, Chapter.title, Chapter.status, Chapter.assigned_agent_id)
                  .where(Chapter.project_id == pid).order_by(Chapter.number)).all()
    return [{"number": n, "title": t, "status": st, "assigned_agent_id": a} for n, t, st, a in rows]


@router.get("/projects/{pid}/runs", response_model=list[RunOut])
def list_runs(pid: str, chapter: Optional[int] = None, agent_id: Optional[str] = None, limit: int = 50,
              s: Session = Depends(get_session)):
    q = select(Run).where(Run.project_id == pid)
    if chapter is not None:
        q = q.where(Run.chapter == chapter)
    if agent_id:
        q = q.where(Run.agent_id == agent_id)
    return [run_out(r) for r in s.exec(q.order_by(Run.created_at.desc()).limit(min(limit, 200))).all()]


@router.get("/projects/{pid}/runs/{rid}", response_model=RunOut)
def read_run(pid: str, rid: str, s: Session = Depends(get_session)):
    r = s.get(Run, rid)
    if not r or r.project_id != pid:
        raise HTTPException(404, "Run not found")
    return run_out(r)


@router.get("/projects/{pid}/chapters/{n}/agent-status")
def chapter_status(pid: str, n: int, s: Session = Depends(get_session)):
    """Everything the writing screen's agent rail needs in one request."""
    _chapter(s, pid, n)
    agents = {a.id: a for a in runtime.ensure_cast(s, pid)}
    runs = list(s.exec(select(Run).where(Run.project_id == pid, Run.chapter == n)
                       .order_by(Run.created_at.desc()).limit(60)).all())
    stages = []
    for task in runtime.PIPELINE:
        r = next((x for x in runs if x.task == task or (task == "edit" and x.task == "revise")), None)
        a = (agents.get(r.agent_id) if r and r.agent_id else None) or runtime.pick_agent(s, pid, task, n)
        stages.append({"task": task, "agent_id": a.id if a else None, "agent_name": a.name if a else "",
                       "role": a.role if a else "", "status": r.status if r else "idle",
                       "run_id": r.id if r else None, "error": r.error if r else ""})
    t = runtime.chapter_thread(s, pid, n)
    obj = s.exec(select(Message).where(Message.thread_id == t.id, Message.intent == "objection")
                 .order_by(Message.created_at.desc())).first()
    last = next((r for r in runs if (r.output or {}).get("context")), None)
    c = (last.output or {}).get("context", {}) if last else {}
    return {
        "thread_id": t.id,
        "stages": stages,
        "objection": None if not obj else {"id": obj.id, "body": obj.body, "sender": obj.sender,
                                           "actions": obj.actions, "created_at": obj.created_at.isoformat()},
        "context": {"memories": c.get("memories", 0), "tokens": c.get("tokens", 0), "codex": c.get("codex", []),
                    "run_id": last.id if last else None, "task": last.task if last else None},
    }
