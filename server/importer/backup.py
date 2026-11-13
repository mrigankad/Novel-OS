"""Whole-book backup (.novelos.zip) and restore as a new project.

The zip holds `book.json` (format_version 1) and `media/<old media id>.<ext>`.
Restore gives every row a fresh id and remaps every foreign key through one
old->new map, so restoring the same file twice yields two independent books.
Connections (API keys) and Runs are never exported.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from sqlmodel import Session, SQLModel, select

from ..models import (
    Agent, BookMetadata, Chapter, ChapterVersion, CodexEntry, CodexLink, ContinuityExemption, CoverDesign,
    Media, Memory, Message, PlotThread, Project, Release, ResearchSource, ResearchTask, Thread, VoiceProfile,
    VoiceSample,
)
from ..models.base import new_id, now
from ..models.codex_extra import CodexProposal
from ..models.publish_extra import MarketingAsset
from ..publish import media as store

FORMAT_VERSION = 1
BOOK_JSON = "book.json"

# Restore order: every table after the tables it points at.
# (key in book.json, model, how rows belong to the project)
TABLES: list[tuple[str, type[SQLModel], str]] = [
    ("agents", Agent, "project"),
    ("media", Media, "project"),
    ("chapters", Chapter, "project"),
    ("versions", ChapterVersion, "chapter"),
    ("codex", CodexEntry, "project"),
    ("codex_links", CodexLink, "project"),
    ("plot_threads", PlotThread, "project"),
    ("exemptions", ContinuityExemption, "project"),
    ("memories", Memory, "project"),
    ("threads", Thread, "project"),
    ("messages", Message, "thread"),
    ("voice_samples", VoiceSample, "project"),
    ("voice_profile", VoiceProfile, "project"),
    ("metadata", BookMetadata, "project"),
    ("covers", CoverDesign, "project"),
    ("releases", Release, "project"),
    ("marketing_assets", MarketingAsset, "project"),
    ("research_tasks", ResearchTask, "project"),
    ("research_sources", ResearchSource, "task"),
    ("codex_proposals", CodexProposal, "project"),
]
# Columns that point at tables we never export: cleared on restore.
NEVER_EXPORTED = {"run", "connection"}


class RestoreError(ValueError):
    pass


def _dump(row: SQLModel) -> dict:
    return row.model_dump(mode="json")


def _rows(session: Session, project_id: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    ids: dict[str, list[str]] = {}
    for key, model, owner in TABLES:
        if owner == "project":
            q = select(model).where(model.project_id == project_id)
        elif owner == "chapter":
            q = select(model).where(model.chapter_id.in_(ids["chapters"]))
        elif owner == "thread":
            q = select(model).where(model.thread_id.in_(ids["threads"]))
        else:
            q = select(model).where(model.task_id.in_(ids["research_tasks"]))
        rows = session.exec(q).all()
        ids[key] = [r.id for r in rows]
        out[key] = [_dump(r) for r in rows]
    return out


def build_backup(session: Session, project_id: str) -> bytes:
    p = session.get(Project, project_id)
    book: dict[str, Any] = {"format_version": FORMAT_VERSION, "exported_at": now().isoformat(),
                            "project": _dump(p), **_rows(session, project_id)}
    for r in book["messages"]:
        r["run_id"] = None  # runs aren't exported
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(BOOK_JSON, json.dumps(book, ensure_ascii=False, indent=1))
        for m in session.exec(select(Media).where(Media.project_id == project_id)).all():
            path = store.file_path(m)
            if path.exists():
                z.write(path, f"media/{m.id}.{path.suffix.lstrip('.')}")
    return buf.getvalue()


def _fk_columns(model: type[SQLModel]) -> dict[str, tuple[str, bool]]:
    """{column: (target table, nullable)} for every foreign key on the model."""
    cols: dict[str, tuple[str, bool]] = {}
    for col in model.__table__.columns:
        for fk in col.foreign_keys:
            cols[col.name] = (fk.column.table.name, bool(col.nullable))
    return cols


def restore_backup(session: Session, data: bytes) -> Project:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        book = json.loads(z.read(BOOK_JSON))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
        raise RestoreError("This isn't a Novel OS backup (.novelos.zip)") from e
    if book.get("format_version") != FORMAT_VERSION:
        raise RestoreError(f"Unsupported backup format {book.get('format_version')!r}")
    media_files = {n.split("/", 1)[1].rsplit(".", 1)[0]: n for n in z.namelist()
                   if n.startswith("media/") and not n.endswith("/")}

    idmap: dict[str, str] = {}
    pdata = dict(book["project"])
    old_pid = pdata.get("id")
    pdata["id"] = idmap[old_pid] = new_id()
    pdata["created_at"] = pdata["updated_at"] = now().isoformat()
    project = Project.model_validate(pdata)
    session.add(project)

    pending_files: list[tuple[Media, bytes]] = []
    for key, model, _owner in TABLES:
        fks = _fk_columns(model)
        rows = book.get(key) or []
        # Pre-assign ids for the whole table so self/forward references within it resolve.
        for r in rows:
            if r.get("id"):
                idmap[r["id"]] = new_id()
        for r in rows:
            r = dict(r)
            old_id = r.get("id")
            r["id"] = idmap.get(old_id) or new_id()
            skip = False
            for col, (target, nullable) in fks.items():
                v = r.get(col)
                if v is None:
                    continue
                if target in NEVER_EXPORTED or v not in idmap:
                    if not nullable:
                        skip = True  # dangling required reference: drop the row
                        break
                    r[col] = None
                else:
                    r[col] = idmap[v]
            if skip:
                continue
            row = model.model_validate(r)
            if model is Media:
                name = media_files.get(old_id)
                if name:
                    pending_files.append((row, z.read(name)))
            session.add(row)
        session.flush()

    for m, blob in pending_files:
        path = store.file_path(m)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    session.commit()
    session.refresh(project)
    return project
