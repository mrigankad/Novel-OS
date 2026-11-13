"""Beta-reader portal: rounds, readers (token links), comments and reading progress."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field, json_field, now


class BetaRound(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    name: str
    chapters: list = json_field([])  # chapter numbers shared in this round
    status: str = Field(default="open", index=True)  # open | closed
    created_at: datetime = created_field()
    closes_at: Optional[datetime] = None


class BetaReader(SQLModel, table=True):
    id: str = id_field()
    round_id: str = fk("betaround")
    name: str
    email: Optional[str] = None
    token: str = Field(index=True, unique=True, max_length=64)
    invited_at: datetime = created_field()
    last_seen_at: Optional[datetime] = None
    furthest_chapter: int = 0
    finished: bool = False


class BetaComment(SQLModel, table=True):
    id: str = id_field()
    round_id: str = fk("betaround")
    reader_id: str = fk("betareader")
    chapter: int = Field(index=True)
    quote: str = ""
    from_offset: Optional[int] = None
    to_offset: Optional[int] = None
    body: str = ""
    reaction: str = Field(default="none", index=True)  # none | love | confused | bored | hooked
    created_at: datetime = created_field()
    resolved: bool = False


class BetaProgress(SQLModel, table=True):
    id: str = id_field()
    reader_id: str = fk("betareader")
    chapter: int = Field(index=True)
    percent: int = 0
    seconds_read: int = 0
    updated_at: datetime = Field(default_factory=now)
