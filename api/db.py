"""Database layer — SQLite via SQLModel.

The agent engine (core/) stays file-based; this DB is the API's system-of-record.
Engine-produced files are mirrored in via `ingest_project`; human-owned content
(Final text, snapshots, comments) is written here directly. All helpers open a
short-lived session from the process-wide engine — fine for a single-process,
single-user local app.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

STAGES = ("outline", "draft", "revised", "final")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _wc(text: str) -> int:
    return len(text.split())


# --------------------------------------------------------------------------- tables

class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str = ""
    genre: str = ""
    author: str = ""
    status: str = "in_progress"
    updated_at: str = Field(default_factory=_now)


class Chapter(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    number: int = Field(index=True)
    title: str = ""
    status: str = ""
    pov: str = ""
    word_count: int = 0
    updated_at: str = Field(default_factory=_now)


class Artifact(SQLModel, table=True):
    """One row per (project, chapter, stage) holding the stage's text."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    stage: str = Field(index=True)  # outline | draft | revised | final
    text: str = ""
    word_count: int = 0
    updated_at: str = Field(default_factory=_now)


class Snapshot(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    label: str = "Manual"
    source: str = "final"
    text: str = ""
    word_count: int = 0
    created_at: str = Field(default_factory=_now)


class Comment(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    body: str = ""
    quote: str = ""
    resolved: bool = False
    created_at: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- engine

_engine = None


def configure(db_url: str) -> None:
    global _engine
    _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)


def _session() -> Session:
    if _engine is None:
        raise RuntimeError("DB not configured. Call db.configure(url) first.")
    return Session(_engine)


# --------------------------------------------------------------------------- ingest

def _stage_file(project_dir: Path, number: int, stage: str) -> Path:
    nnn = f"{number:03d}"
    out = project_dir / "outputs"
    if stage == "outline":
        return out / f"chapter_{nnn}_outline.md"
    return out / "manuscript" / f"chapter_{nnn}_{stage}.md"


def ingest_project(root: Path, project_id: str) -> None:
    """Mirror a project's filesystem state + stage files into the DB (upsert)."""
    project_dir = Path(root) / project_id
    state_file = project_dir / "outputs" / "state" / "story_state.json"
    if not state_file.exists():
        return
    data = json.loads(state_file.read_text(encoding="utf-8"))
    meta = data.get("metadata", {})
    chapters = data.get("chapters", {})

    with _session() as s:
        proj = s.get(Project, project_id)
        if proj is None:
            proj = Project(id=project_id)
        proj.title = meta.get("title", project_id)
        proj.genre = meta.get("genre", "")
        proj.author = meta.get("author", "")
        proj.status = meta.get("status", "in_progress")
        proj.updated_at = _now()
        s.add(proj)

        for key, ch in chapters.items():
            number = int(ch.get("number", key))
            row = s.exec(
                select(Chapter).where(Chapter.project_id == project_id, Chapter.number == number)
            ).first()
            if row is None:
                row = Chapter(project_id=project_id, number=number)
            row.title = ch.get("title", "") or ""
            row.status = ch.get("status", "") or ""
            row.pov = ch.get("pov_character", "") or ""
            row.word_count = int(ch.get("word_count", 0) or 0)
            row.updated_at = _now()
            s.add(row)

            for stage in STAGES:
                # Final is DB-owned: don't let an (older) file clobber a saved Final.
                f = _stage_file(project_dir, number, stage)
                if not f.exists():
                    continue
                text = f.read_text(encoding="utf-8")
                art = _get_artifact(s, project_id, number, stage)
                if stage == "final" and art is not None:
                    continue
                if art is None:
                    art = Artifact(project_id=project_id, chapter=number, stage=stage)
                art.text = text
                art.word_count = _wc(text)
                art.updated_at = _now()
                s.add(art)
        s.commit()


def _get_artifact(s: Session, project_id: str, chapter: int, stage: str) -> Optional[Artifact]:
    return s.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.chapter == chapter,
            Artifact.stage == stage,
        )
    ).first()


def upsert_artifact(project_id: str, chapter: int, stage: str, text: str) -> None:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is None:
            art = Artifact(project_id=project_id, chapter=chapter, stage=stage)
        art.text = text
        art.word_count = _wc(text)
        art.updated_at = _now()
        s.add(art)
        s.commit()


def delete_artifact(project_id: str, chapter: int, stage: str) -> None:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is not None:
            s.delete(art)
            s.commit()


def get_artifact_text(project_id: str, chapter: int, stage: str) -> Optional[str]:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        return art.text if art else None


# --------------------------------------------------------------------------- snapshots

def snapshots_list(project_id: str, chapter: int) -> list[Snapshot]:
    with _session() as s:
        rows = s.exec(
            select(Snapshot)
            .where(Snapshot.project_id == project_id, Snapshot.chapter == chapter)
            .order_by(Snapshot.created_at.desc())
        ).all()
        return list(rows)


def snapshot_create(project_id: str, chapter: int, text: str, label: str, source: str) -> Snapshot:
    with _session() as s:
        snap = Snapshot(
            project_id=project_id, chapter=chapter, text=text,
            label=label, source=source, word_count=_wc(text),
        )
        s.add(snap)
        s.commit()
        s.refresh(snap)
        return snap


def snapshot_get(project_id: str, chapter: int, snap_id: str) -> Optional[Snapshot]:
    with _session() as s:
        snap = s.get(Snapshot, snap_id)
        if snap and snap.project_id == project_id and snap.chapter == chapter:
            return snap
        return None


def snapshot_delete(project_id: str, chapter: int, snap_id: str) -> bool:
    with _session() as s:
        snap = s.get(Snapshot, snap_id)
        if not snap or snap.project_id != project_id or snap.chapter != chapter:
            return False
        s.delete(snap)
        s.commit()
        return True


# --------------------------------------------------------------------------- comments

def comments_list(project_id: str, chapter: int) -> list[Comment]:
    with _session() as s:
        rows = s.exec(
            select(Comment)
            .where(Comment.project_id == project_id, Comment.chapter == chapter)
            .order_by(Comment.created_at.desc())
        ).all()
        return list(rows)


def comment_add(project_id: str, chapter: int, body: str, quote: str = "") -> Comment:
    with _session() as s:
        c = Comment(project_id=project_id, chapter=chapter, body=body, quote=quote)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def comment_update(project_id: str, chapter: int, cid: str, resolved: bool) -> Optional[Comment]:
    with _session() as s:
        c = s.get(Comment, cid)
        if not c or c.project_id != project_id or c.chapter != chapter:
            return None
        c.resolved = resolved
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def comment_delete(project_id: str, chapter: int, cid: str) -> bool:
    with _session() as s:
        c = s.get(Comment, cid)
        if not c or c.project_id != project_id or c.chapter != chapter:
            return False
        s.delete(c)
        s.commit()
        return True


def chapter_delete_all(project_id: str, number: int) -> None:
    """Remove DB rows for one chapter (artifacts, snapshots, comments, chapter row)."""
    with _session() as s:
        s.exec(delete(Artifact).where(
            Artifact.project_id == project_id, Artifact.chapter == number,
        ))
        s.exec(delete(Snapshot).where(
            Snapshot.project_id == project_id, Snapshot.chapter == number,
        ))
        s.exec(delete(Comment).where(
            Comment.project_id == project_id, Comment.chapter == number,
        ))
        s.exec(delete(Chapter).where(
            Chapter.project_id == project_id, Chapter.number == number,
        ))
        s.commit()


def _set_chapter_number(s: Session, project_id: str, from_num: int, to_num: int) -> None:
    for model in (Artifact, Snapshot, Comment):
        rows = s.exec(
            select(model).where(model.project_id == project_id, model.chapter == from_num)
        ).all()
        for row in rows:
            row.chapter = to_num
            s.add(row)
    ch_row = s.exec(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.number == from_num)
    ).first()
    if ch_row is not None:
        ch_row.number = to_num
        s.add(ch_row)


def chapter_reassign(project_id: str, from_num: int, to_num: int, *, swap: bool = False) -> None:
    """Update DB rows when a chapter number changes (move or swap)."""
    with _session() as s:
        if swap:
            sentinel = -(max(from_num, to_num) + 100000)
            _set_chapter_number(s, project_id, from_num, sentinel)
            _set_chapter_number(s, project_id, to_num, from_num)
            _set_chapter_number(s, project_id, sentinel, to_num)
        else:
            _set_chapter_number(s, project_id, from_num, to_num)
        s.commit()


def project_delete(project_id: str) -> None:
    """Remove all DB rows for a project."""
    with _session() as s:
        s.exec(delete(Artifact).where(Artifact.project_id == project_id))
        s.exec(delete(Snapshot).where(Snapshot.project_id == project_id))
        s.exec(delete(Comment).where(Comment.project_id == project_id))
        s.exec(delete(Chapter).where(Chapter.project_id == project_id))
        s.exec(delete(Project).where(Project.id == project_id))
        s.commit()


def export_project_data(project_id: str) -> dict:
    """Serialize all DB rows for a project (for backup archives)."""
    with _session() as s:
        proj = s.get(Project, project_id)
        if proj is None:
            return {"version": 1, "project_id": project_id, "project": None,
                    "chapters": [], "artifacts": [], "snapshots": [], "comments": []}
        chapters = list(s.exec(select(Chapter).where(Chapter.project_id == project_id)).all())
        artifacts = list(s.exec(select(Artifact).where(Artifact.project_id == project_id)).all())
        snapshots = list(s.exec(select(Snapshot).where(Snapshot.project_id == project_id)).all())
        comments = list(s.exec(select(Comment).where(Comment.project_id == project_id)).all())
        return {
            "version": 1,
            "project_id": project_id,
            "project": proj.model_dump(),
            "chapters": [c.model_dump() for c in chapters],
            "artifacts": [a.model_dump() for a in artifacts],
            "snapshots": [sn.model_dump() for sn in snapshots],
            "comments": [c.model_dump() for c in comments],
        }


def import_project_data(
    project_id: str,
    data: dict,
    *,
    allow_id_mismatch: bool = False,
    remap_ids: bool = False,
) -> None:
    """Replace all DB rows for a project from a backup export."""
    if (
        not allow_id_mismatch
        and data.get("project_id")
        and data["project_id"] != project_id
    ):
        raise ValueError(
            f"Backup belongs to project {data['project_id']!r}, not {project_id!r}"
        )
    with _session() as s:
        s.exec(delete(Artifact).where(Artifact.project_id == project_id))
        s.exec(delete(Snapshot).where(Snapshot.project_id == project_id))
        s.exec(delete(Comment).where(Comment.project_id == project_id))
        s.exec(delete(Chapter).where(Chapter.project_id == project_id))
        s.exec(delete(Project).where(Project.id == project_id))

        proj_data = data.get("project")
        if proj_data:
            proj = Project(**proj_data)
            proj.id = project_id
            s.add(proj)

        for row in data.get("chapters", []):
            ch = Chapter(**row)
            if remap_ids:
                ch.id = _new_id()
            ch.project_id = project_id
            s.add(ch)
        for row in data.get("artifacts", []):
            art = Artifact(**row)
            if remap_ids:
                art.id = _new_id()
            art.project_id = project_id
            s.add(art)
        for row in data.get("snapshots", []):
            snap = Snapshot(**row)
            if remap_ids:
                snap.id = _new_id()
            snap.project_id = project_id
            s.add(snap)
        for row in data.get("comments", []):
            com = Comment(**row)
            if remap_ids:
                com.id = _new_id()
            com.project_id = project_id
            s.add(com)
        s.commit()


def sync_artifacts_to_files(root: Path, project_id: str) -> None:
    """Write DB artifact text back to stage files on disk."""
    project_dir = root / project_id
    with _session() as s:
        arts = list(s.exec(select(Artifact).where(Artifact.project_id == project_id)).all())
    for art in arts:
        path = _stage_file(project_dir, art.chapter, art.stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(art.text, encoding="utf-8")
        os.replace(tmp, path)


def _clear_all() -> None:
    """Test helper — wipe every table."""
    with _session() as s:
        for model in (Artifact, Snapshot, Comment, Chapter, Project):
            s.exec(delete(model))
        s.commit()
