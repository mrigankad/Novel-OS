"""Shared column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def id_field() -> str:
    return Field(default_factory=new_id, primary_key=True, max_length=32)


def created_field() -> datetime:
    return Field(default_factory=now, index=True)


def json_field(default=None):
    """A JSON column (dict or list). Works on SQLite and Postgres."""
    factory = (lambda: {}) if default is None else (lambda: type(default)(default))
    return Field(default_factory=factory, sa_column=Column(JSON, nullable=False))


def fk(table: str, *, nullable: bool = False, index: bool = True):
    return Field(
        default=None if nullable else ...,
        foreign_key=f"{table}.id",
        index=index,
        nullable=nullable,
        ondelete="CASCADE",
    )
