"""Research, voice, publishing and studio-wide settings."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field, json_field, now


# --------------------------------------------------------------- research swarm

class ResearchTask(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    question: str
    chapter: Optional[int] = None
    status: str = "queued"  # queued | browsing | synthesizing | done | failed
    progress: str = ""  # human-readable current step
    summary: str = ""
    created_at: datetime = created_field()
    finished_at: Optional[datetime] = None


class ResearchSource(SQLModel, table=True):
    id: str = id_field()
    task_id: str = fk("researchtask")
    url: str
    title: str = ""
    excerpt: str = ""  # short quoted passage (<= 300 chars)
    note: str = ""  # what it tells us, in our words
    reliability: float = 0.5
    filed_to_codex_id: Optional[str] = Field(default=None, foreign_key="codexentry.id", nullable=True)
    created_at: datetime = created_field()


# --------------------------------------------------------------- voice lab

class VoiceSample(SQLModel, table=True):
    """Writing the author supplied (or approved chapters) that define their voice."""

    id: str = id_field()
    project_id: str = fk("project")
    title: str = ""
    text: str
    word_count: int = 0
    source: str = "upload"  # upload | chapter:<n>
    created_at: datetime = created_field()


class VoiceProfile(SQLModel, table=True):
    """The extracted Voice DNA: measured traits plus signature moves and rules."""

    id: str = id_field()
    project_id: str = Field(foreign_key="project.id", unique=True, ondelete="CASCADE")
    traits: dict = json_field()  # {"sentence_len": {"mean": 17, ...}, "dialogue_ratio": 0.22, ...}
    signature_moves: list = json_field([])  # [{"example": "...", "note": "..."}]
    never: list = json_field([])  # ["suddenly", "dream openings"]
    lift: str = "me_plus_lift"  # pure_me | me_plus_lift | experiment
    style_guide: str = ""  # compact prose guide injected into Scribe/Curator prompts
    words_analyzed: int = 0
    updated_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------- publishing

class BookMetadata(SQLModel, table=True):
    """One record synced to every store."""

    id: str = id_field()
    project_id: str = Field(foreign_key="project.id", unique=True, ondelete="CASCADE")
    subtitle: str = ""
    series: str = ""
    series_number: Optional[int] = None
    description: str = ""
    keywords: list = json_field([])
    bisac: list = json_field([])
    isbn_ebook: str = ""
    isbn_print: str = ""
    language: str = "en"
    price: dict = json_field()
    comps: list = json_field([])
    updated_at: datetime = Field(default_factory=now)


class CoverDesign(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    format: str = "paperback"  # ebook | paperback | hardcover | audiobook
    trim: str = "5.5x8.5"
    paper: str = "cream"  # cream | white | color
    front_media_id: Optional[str] = Field(default=None, foreign_key="media.id", nullable=True)
    back_copy: str = ""
    spine_text: str = ""
    colors: dict = json_field()
    layout: dict = json_field()
    selected: bool = False
    created_at: datetime = created_field()


class Release(SQLModel, table=True):
    """Per-store launch status."""

    id: str = id_field()
    project_id: str = fk("project")
    store: str  # kdp | ingram | d2d | google | apple | kobo | audiobook | beta | query
    status: str = "todo"  # todo | ready | submitted | live | blocked
    checklist: dict = json_field()
    notes: str = ""
    updated_at: datetime = Field(default_factory=now)


# --------------------------------------------------------------- settings

class Connection(SQLModel, table=True):
    """A model provider the studio can use. Keys live here, never sent to the browser."""

    id: str = id_field()
    provider: str = Field(index=True, unique=True)  # ollama | ollama_cloud | anthropic | openai | ...
    label: str = ""
    base_url: str = ""
    api_key: str = ""  # stored locally; API responses only expose `has_key`
    default_model: str = ""
    is_default: bool = False
    created_at: datetime = created_field()
