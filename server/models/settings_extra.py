"""Studio-wide settings tables. Owner: connections area."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from .base import id_field, now


class RoleDefault(SQLModel, table=True):
    """Which connection/model a role uses unless a book's Agent overrides it.

    Empty provider means "fall through to the default connection"."""

    id: str = id_field()
    role: str = Field(index=True, unique=True)  # architect | scribe | editor | guardian | curator | researcher
    provider: str = ""
    model: str = ""
    temperature: float = 0.7
    updated_at: datetime = Field(default_factory=now)
