"""Prompts and the token-conscious context pack every agent run gets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from ..models import Agent, Chapter, CodexEntry, Memory, PlotThread, Project
from ..services.voice import get_style_guide
from . import memory as mem

ROOT = Path(__file__).resolve().parents[2]

ROLE_PROMPT_DIR = {
    "architect": "architect",
    "scribe": "scribe",
    "editor": "editor",
    "guardian": "continuity_guardian",
    "curator": "style_curator",
}

RESEARCHER_PROMPT = (
    "You are the Researcher on a novel-writing team. You find and summarise real-world facts the book "
    "depends on (history, science, places, professions), flag what is uncertain, and keep answers short "
    "and cited where possible."
)

DEFAULT_TASK = {"architect": "plan", "scribe": "draft", "editor": "edit", "guardian": "check",
                "curator": "voice", "researcher": "chat"}
TASK_ROLE = {"plan": "architect", "draft": "scribe", "revise": "editor", "edit": "editor",
             "check": "guardian", "voice": "curator", "chat": "scribe"}
VOICE_TASKS = {"draft", "revise", "edit", "voice", "chat"}


@lru_cache(maxsize=16)
def role_prompt(role: str, with_contract: bool = True) -> str:
    d = ROLE_PROMPT_DIR.get(role)
    if not d:
        return RESEARCHER_PROMPT if role == "researcher" else "You are a helpful member of a novel-writing team."
    p = ROOT / "agents" / d / "prompt.md"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return f"You are the {role} on a novel-writing team."
    if not with_contract:
        text = re.split(r"^#+\s*OUTPUT CONTRACT", text, flags=re.M)[0]
    return text.strip()


def est_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def last_words(text: str, n: int = 400) -> str:
    words = (text or "").split()
    return " ".join(words[-n:])


@dataclass
class ContextPack:
    system: str
    user: str
    memories: list[Memory] = field(default_factory=list)
    codex: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return est_tokens(self.system) + est_tokens(self.user)

    def meta(self) -> dict:
        return {"memories": len(self.memories), "memory_ids": [m.id for m in self.memories],
                "codex": self.codex, "tokens": self.tokens}


def _beats_text(beats: list) -> str:
    lines = []
    for b in beats or []:
        if isinstance(b, dict):
            b = b.get("text") or b.get("summary") or b.get("title") or ""
        if b:
            lines.append(f"- {b}")
    return "\n".join(lines)


def relevant_codex(session: Session, project_id: str, haystack: str, limit: int = 12) -> list[CodexEntry]:
    hay = (haystack or "").lower()
    if not hay:
        return []
    out = []
    for e in session.exec(select(CodexEntry).where(CodexEntry.project_id == project_id)).all():
        names = [e.name] + [a for a in (e.aliases or []) if isinstance(a, str)]
        if any(n and re.search(rf"\b{re.escape(n.lower())}\b", hay) for n in names):
            out.append(e)
        if len(out) >= limit:
            break
    return out


def build(session: Session, project_id: str, agent: Agent, task: str, chapter: Optional[int],
          instruction: str = "", transcript: str = "", task_spec: str = "") -> ContextPack:
    project = session.get(Project, project_id)
    ch = None
    prev = None
    if chapter is not None:
        ch = session.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == chapter)).first()
        prev = session.exec(select(Chapter).where(Chapter.project_id == project_id,
                                                  Chapter.number == chapter - 1)).first()

    sys_parts = [role_prompt(agent.role, with_contract=task not in ("chat",))]
    if agent.brief:
        sys_parts.append(f"## Your brief from the author\n{agent.brief}")
    if agent.use_voice_dna and task in VOICE_TASKS:
        guide = get_style_guide(session, project_id)
        if guide:
            sys_parts.append(f"## Voice DNA: the author's style guide\n{guide}")
    system = "\n\n".join(sys_parts)

    user_parts: list[str] = []
    if project:
        bits = [f"Title: {project.title}"]
        if project.genre:
            bits.append(f"Genre: {project.genre}")
        if project.premise:
            bits.append(f"Premise: {project.premise}")
        for k, v in list((project.bible or {}).items())[:8]:
            if isinstance(v, (str, int, float)) and str(v):
                bits.append(f"{k}: {str(v)[:300]}")
        user_parts.append("## Book\n" + "\n".join(bits))

    query = " ".join(x for x in [instruction, ch.synopsis if ch else "", _beats_text(ch.beats) if ch else ""] if x)
    memories = mem.recall(session, project_id, query or (ch.title if ch else task), agent_id=agent.id,
                          chapter=chapter, k=12)
    if memories:
        user_parts.append("## What you remember\n" + "\n".join(
            f"- [{m.kind}{' · ch ' + str(m.chapter) if m.chapter else ''}] {m.content}" for m in memories))

    if ch:
        lines = [f"Chapter {ch.number}" + (f": {ch.title}" if ch.title else "")]
        if ch.pov:
            lines.append(f"POV: {ch.pov}")
        if ch.synopsis:
            lines.append(f"Synopsis: {ch.synopsis}")
        bt = _beats_text(ch.beats)
        if bt:
            lines.append("Beats:\n" + bt)
        lines.append(f"Target length: about {ch.target_words} words")
        user_parts.append("## This chapter\n" + "\n".join(lines))
    if prev and prev.text:
        user_parts.append(f"## End of the previous chapter (ch {prev.number})\n...{last_words(prev.text)}")

    hay = " ".join([query, (ch.text[-6000:] if ch and ch.text else ""), instruction, transcript])
    codex = relevant_codex(session, project_id, hay)
    if codex:
        user_parts.append("## Codex\n" + "\n".join(
            f"- {e.name} ({e.kind}{', ' + e.role if e.role else ''}): {e.summary[:240]}"
            + (f" Facts: {', '.join(f'{k}={v}' for k, v in list((e.facts or {}).items())[:6])}" if e.facts else "")
            for e in codex))

    threads = session.exec(select(PlotThread).where(PlotThread.project_id == project_id, PlotThread.status == "open")
                           .order_by(PlotThread.priority).limit(8)).all()
    if threads:
        user_parts.append("## Open plot threads\n" + "\n".join(
            f"- {t.name} ({t.kind})" + (f": {t.notes[:160]}" if t.notes else "") for t in threads))

    if task in ("edit", "revise", "check", "voice") and ch and ch.text:
        user_parts.append(f"## Current chapter text\n{ch.text}")
    if transcript:
        user_parts.append(f"## Recent conversation in the writers' room\n{transcript}")
    if task_spec:
        user_parts.append(f"## Your task\n{task_spec}")
    if instruction:
        user_parts.append(f"## Note from the author\n{instruction}")

    return ContextPack(system=system, user="\n\n".join(user_parts), memories=memories,
                       codex=[e.name for e in codex])
