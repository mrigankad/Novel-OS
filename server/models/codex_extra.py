"""Codex auto-extraction: entries proposed from the chapters, awaiting the author."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field


class CodexProposal(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    name: str = Field(index=True)
    # character | location | item | lore | faction | event
    kind: str = "character"
    summary: str = ""
    first_chapter: Optional[int] = None
    evidence: str = ""  # verbatim quote from the manuscript, <= 200 chars
    # open | accepted | dismissed (dismissed names are never proposed again)
    status: str = Field(default="open", index=True)
    created_at: datetime = created_field()
