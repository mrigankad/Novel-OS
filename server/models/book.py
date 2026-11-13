"""The book: projects, chapters, versions, Codex, continuity exemptions, media."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from .base import created_field, fk, id_field, json_field, now


class Project(SQLModel, table=True):
    id: str = id_field()
    title: str
    author: str = ""
    genre: str = ""
    premise: str = ""
    # Story bible: tone, themes, setting, world rules, POV/tense, target length.
    bible: dict = json_field()
    target_words: int = 90_000
    status: str = "drafting"  # planning | drafting | revising | publishing | published
    created_at: datetime = created_field()
    updated_at: datetime = Field(default_factory=now)


class Chapter(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("project_id", "number"),)

    id: str = id_field()
    project_id: str = fk("project")
    number: int = Field(index=True)
    title: str = ""
    act: int = 1
    pov: str = ""
    # planned | drafting | drafted | revising | final
    status: str = "planned"
    synopsis: str = ""
    beats: list = json_field([])
    # Canonical text (Markdown) and the editor document (ProseMirror JSON).
    text: str = ""
    doc: dict = json_field()
    word_count: int = 0
    target_words: int = 3000
    assigned_agent_id: Optional[str] = Field(default=None, foreign_key="agent.id", nullable=True)
    updated_at: datetime = Field(default_factory=now)


class ChapterVersion(SQLModel, table=True):
    """Immutable history: every agent pass and every manual snapshot."""

    id: str = id_field()
    chapter_id: str = fk("chapter")
    # outline | draft | revision | edit | snapshot | final
    kind: str = "snapshot"
    text: str = ""
    word_count: int = 0
    produced_by: str = "author"  # author | agent:<id>
    model: str = ""
    note: str = ""
    created_at: datetime = created_field()


class CodexEntry(SQLModel, table=True):
    """Characters, places, items, lore, factions, events: the book's facts."""

    id: str = id_field()
    project_id: str = fk("project")
    # character | location | item | lore | faction | event | theme
    kind: str = Field(index=True)
    name: str = Field(index=True)
    aliases: list = json_field([])
    role: str = ""  # protagonist | antagonist | supporting | minor
    summary: str = ""
    # Structured facts: {"eye_color": "grey", "status": "alive", "location": "north orchard"}
    facts: dict = json_field()
    notes: str = ""
    image_media_id: Optional[str] = Field(default=None, foreign_key="media.id", nullable=True)
    first_chapter: Optional[int] = None
    last_chapter: Optional[int] = None
    created_at: datetime = created_field()
    updated_at: datetime = Field(default_factory=now)


class CodexLink(SQLModel, table=True):
    """Relationship edge between two Codex entries."""

    id: str = id_field()
    project_id: str = fk("project")
    source_id: str = fk("codexentry")
    target_id: str = fk("codexentry")
    label: str = ""  # sister, rival, owns, located in...
    since_chapter: Optional[int] = None


class PlotThread(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    name: str
    kind: str = "subplot"  # main | subplot | mystery | romance | arc
    status: str = "open"  # open | resolved | dropped
    priority: int = 2
    planted_chapter: Optional[int] = None
    target_chapter: Optional[int] = None
    last_advanced_chapter: Optional[int] = None
    notes: str = ""


class ContinuityExemption(SQLModel, table=True):
    """'This is intentional': a finding the author has ruled on."""

    id: str = id_field()
    project_id: str = fk("project")
    finding_key: str = Field(index=True)
    reason: str = ""
    created_at: datetime = created_field()


class Media(SQLModel, table=True):
    """Imported or generated images (portraits, maps, mood boards, covers)."""

    id: str = id_field()
    project_id: str = fk("project")
    filename: str = ""
    content_type: str = ""
    sha256: str = Field(index=True)
    size: int = 0
    width: int = 0
    height: int = 0
    kind: str = "image"  # image | cover | portrait | map | reference
    caption: str = ""
    tags: list = json_field([])
    source: str = "upload"  # upload | generated | research
    created_at: datetime = created_field()
