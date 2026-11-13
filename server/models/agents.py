"""Agents, their memory, and the writers' room where they talk."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field, json_field, now


class Agent(SQLModel, table=True):
    """A configured agent on a project: a role plus a model plus a brief."""

    id: str = id_field()
    project_id: str = fk("project")
    # architect | scribe | editor | guardian | curator | researcher | custom
    role: str = Field(index=True)
    name: str
    brief: str = ""  # extra instructions appended to the role prompt
    # Model routing: empty means "use the studio default connection".
    provider: str = ""
    model: str = ""
    temperature: float = 0.7
    use_voice_dna: bool = True
    autonomy: str = "ask"  # ask | autopilot
    enabled: bool = True
    created_at: datetime = created_field()


class Memory(SQLModel, table=True):
    """Long-term agent memory.

    agent_id NULL means shared project memory every agent can recall.
    kind: fact (canon), decision (author ruling), preference (how the author
    likes things), episode (what happened in a run), summary (chapter recap),
    style (voice observation), research (cited finding).
    """

    id: str = id_field()
    project_id: str = fk("project")
    agent_id: Optional[str] = Field(default=None, foreign_key="agent.id", index=True, nullable=True,
                                    ondelete="CASCADE")
    kind: str = Field(index=True)
    content: str
    chapter: Optional[int] = Field(default=None, index=True)
    source: str = ""  # message:<id> | chapter:<n> | research:<id> | author
    importance: float = 0.5  # 0..1, used in recall ranking
    pinned: bool = False
    embedding: Optional[list] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = created_field()
    last_recalled_at: Optional[datetime] = None
    recall_count: int = 0


class Thread(SQLModel, table=True):
    """A conversation: the writers' room for a chapter, or a direct chat."""

    id: str = id_field()
    project_id: str = fk("project")
    title: str = ""
    chapter: Optional[int] = Field(default=None, index=True)
    kind: str = "room"  # room | direct | research
    created_at: datetime = created_field()
    updated_at: datetime = Field(default_factory=now)


class Message(SQLModel, table=True):
    id: str = id_field()
    thread_id: str = fk("thread")
    # author | agent:<id> | system
    sender: str
    # agent ids this message is addressed to (from @mentions or handoffs)
    recipients: list = json_field([])
    body: str
    # handoff | objection | proposal | question | note | result
    intent: str = "note"
    # quick replies the author can click: [{"label": "...", "action": "..."}]
    actions: list = json_field([])
    run_id: Optional[str] = Field(default=None, foreign_key="run.id", nullable=True)
    created_at: datetime = created_field()


class Run(SQLModel, table=True):
    """One agent job (draft a chapter, check continuity, research a question)."""

    id: str = id_field()
    project_id: str = fk("project")
    agent_id: Optional[str] = Field(default=None, foreign_key="agent.id", nullable=True, ondelete="SET NULL")
    task: str  # draft | revise | edit | check | plan | research | voice | chat
    chapter: Optional[int] = None
    status: str = "queued"  # queued | running | done | failed | cancelled
    input: dict = json_field()
    output: dict = json_field()
    error: str = ""
    provider: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: datetime = created_field()
    finished_at: Optional[datetime] = None
