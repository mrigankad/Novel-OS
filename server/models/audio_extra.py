"""Audiobook studio: voice cast, pronunciation dictionary and rendered chapter tracks."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field


class AudioCast(SQLModel, table=True):
    """A voice. codex_entry_id None is the narrator."""

    id: str = id_field()
    project_id: str = fk("project")
    codex_entry_id: Optional[str] = fk("codexentry", nullable=True)
    provider: str = ""
    voice: str = ""
    style_instructions: str = ""


class Pronunciation(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    term: str = ""
    say_as: str = ""


class AudioTrack(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    chapter: int = Field(index=True)
    provider: str = ""
    voice: str = ""
    duration_s: float = 0.0
    size: int = 0
    path: str = ""
    text_sha: str = ""
    created_at: datetime = created_field()
