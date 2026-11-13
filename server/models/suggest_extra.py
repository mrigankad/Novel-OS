"""Inline Editor suggestions: line-level track-changes on a chapter."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field


class Suggestion(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    chapter: int = Field(index=True)
    run_id: Optional[str] = Field(default=None, index=True, nullable=True)
    quote: str = ""  # the exact original span
    replacement: str = ""
    reason: str = ""
    # tighten | clarity | voice | continuity | grammar
    kind: str = "clarity"
    # open | accepted | dismissed
    status: str = Field(default="open", index=True)
    created_at: datetime = created_field()
