"""Ship area extras: generated marketing copy (and cover concept briefs)."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from .base import created_field, fk, id_field


class MarketingAsset(SQLModel, table=True):
    id: str = id_field()
    project_id: str = fk("project")
    # blurb | taglines | query_letter | synopsis_1p | newsletter | a_plus_copy | cover_concepts
    kind: str = Field(index=True)
    content: str = ""
    model: str = ""
    created_at: datetime = created_field()
