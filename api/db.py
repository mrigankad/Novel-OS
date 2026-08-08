"""Database layer SQLite via SQLModel.

The agent engine (core/) stays file-based; this DB is the API's system-of-record.
Engine-produced files are mirrored in via `ingest_project`; human-owned content
(Final text, snapshots, comments) is written here directly. All helpers open a
short-lived session from the process-wide engine fine for a single-process,
single-user local app.
"""

from __future__ import annotations

import json
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
    """One row per (project, chapter, stage) holding the stage's text.

    `doc_json` carries the ProseMirror document for Final (PLAN.md P1). It is
    the canonical form; `text` is the markdown projection agents read, and is
    regenerated from the document on every save. Drafts and revisions stay
    markdown-only immutable provenance.
    """
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    stage: str = Field(index=True)  # outline | draft | revised | final
    text: str = ""
    doc_json: str = ""
    word_count: int = 0
    updated_at: str = Field(default_factory=_now)
    # P3.2 pipeline provenance
    produced_by_agent: str = ""
    produced_by_model: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""


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
    """A note on a chapter. Pre-P1 comments only had `quote`; P1 adds
    ProseMirror-ish character offsets (`from_pos`/`to_pos`) so the note can
    survive edits. `anchor_status` is `ok` when positions resolve, or
    `unresolved` when the quoted span can no longer be found."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    body: str = ""
    quote: str = ""
    from_pos: Optional[int] = None
    to_pos: Optional[int] = None
    anchor_status: str = "ok"  # ok | unresolved
    persona: str = "author"  # author | editor | beta (P3.3 single-writer personas)
    resolved: bool = False
    created_at: str = Field(default_factory=_now)


class Media(SQLModel, table=True):
    """Metadata for an uploaded image. The bytes live in a MediaStore,
    addressed by `sha`; this row is the only thing that knows the original
    filename. `kind` marks what the image is for (codex portrait, research
    moodboard, inline manuscript image) so views can filter without a join."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    sha: str = Field(index=True)
    ext: str = ""
    filename: str = ""
    content_type: str = ""
    size: int = 0
    width: int = 0
    height: int = 0
    kind: str = Field(default="general", index=True)
    alt: str = ""
    created_at: str = Field(default_factory=_now)


# ----------------------------------------------------------------- tenancy tables
# Schema only P7 adds auth on top. Defined now so features are not built
# against a single-tenant assumption that would later have to be unpicked.
# These tables record who may see a project; the story itself stays in files.

class Workspace(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str = ""
    slug: str = Field(default="", index=True)
    created_at: str = Field(default_factory=_now)


class User(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    email: str = Field(default="", index=True)
    display_name: str = ""
    created_at: str = Field(default_factory=_now)


class Membership(SQLModel, table=True):
    """A user's role in a workspace. owner > editor > viewer."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    user_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    role: str = "owner"
    created_at: str = Field(default_factory=_now)


class ProjectOwnership(SQLModel, table=True):
    """Binds a project directory to the workspace that owns it."""
    project_id: str = Field(primary_key=True)
    workspace_id: str = Field(index=True)
    created_at: str = Field(default_factory=_now)


class AuthSession(SQLModel, table=True):
    """Placeholder for P7. Present so session lookup has a home from the start."""
    token: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    expires_at: str = ""
    created_at: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- engine

_engine = None


# Columns added to tables that already exist in the wild. `create_all` only
# creates missing tables it will not alter an existing one so a new column
# on a shipped table needs an explicit ALTER. Additive only: never drop or
# retype, so an older build can still read the database.
_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    # (table, column, DDL type + default)
    ("artifact", "doc_json", "TEXT DEFAULT ''"),
    ("artifact", "produced_by_agent", "TEXT DEFAULT ''"),
    ("artifact", "produced_by_model", "TEXT DEFAULT ''"),
    ("artifact", "reviewed_by", "TEXT DEFAULT ''"),
    ("artifact", "reviewed_at", "TEXT DEFAULT ''"),
    ("comment", "from_pos", "INTEGER"),
    ("comment", "to_pos", "INTEGER"),
    ("comment", "anchor_status", "TEXT DEFAULT 'ok'"),
    ("comment", "persona", "TEXT DEFAULT 'author'"),
)


def _run_migrations(engine) -> None:
    from sqlalchemy import text as _sql

    with engine.begin() as conn:
        for table, column, ddl in _MIGRATIONS:
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue  # table not created yet; create_all made it correctly
            if column not in existing:
                conn.execute(_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _connect_args_for(db_url: str) -> dict:
    """SQLite needs check_same_thread=False; Postgres must not get that kwarg."""
    url = (db_url or "").lower()
    if url.startswith("sqlite:"):
        return {"check_same_thread": False}
    return {}


def configure(db_url: str) -> None:
    global _engine
    _engine = create_engine(db_url, connect_args=_connect_args_for(db_url))
    SQLModel.metadata.create_all(_engine)
    _run_migrations(_engine)


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


def upsert_artifact(
    project_id: str,
    chapter: int,
    stage: str,
    text: str,
    doc_json: Optional[str] = None,
    *,
    produced_by_agent: Optional[str] = None,
    produced_by_model: Optional[str] = None,
    reviewed_by: Optional[str] = None,
    reviewed_at: Optional[str] = None,
) -> None:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is None:
            art = Artifact(project_id=project_id, chapter=chapter, stage=stage)
        art.text = text
        if doc_json is not None:
            art.doc_json = doc_json
        art.word_count = _wc(text)
        art.updated_at = _now()
        if produced_by_agent is not None:
            art.produced_by_agent = produced_by_agent
        if produced_by_model is not None:
            art.produced_by_model = produced_by_model
        if reviewed_by is not None:
            art.reviewed_by = reviewed_by
        if reviewed_at is not None:
            art.reviewed_at = reviewed_at
        s.add(art)
        s.commit()


def get_artifact(project_id: str, chapter: int, stage: str) -> Optional[Artifact]:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is None:
            return None
        # Detach fields we need outside the session
        return Artifact(
            id=art.id,
            project_id=art.project_id,
            chapter=art.chapter,
            stage=art.stage,
            text=art.text,
            doc_json=art.doc_json,
            word_count=art.word_count,
            updated_at=art.updated_at,
            produced_by_agent=getattr(art, "produced_by_agent", "") or "",
            produced_by_model=getattr(art, "produced_by_model", "") or "",
            reviewed_by=getattr(art, "reviewed_by", "") or "",
            reviewed_at=getattr(art, "reviewed_at", "") or "",
        )


def get_artifact_text(project_id: str, chapter: int, stage: str) -> Optional[str]:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        return art.text if art else None


def get_artifact_doc(project_id: str, chapter: int, stage: str) -> Optional[str]:
    """The stored ProseMirror JSON, or None if this stage has never been saved
    as rich text (every pre-P1 Final, and all drafts/revisions)."""
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        return (art.doc_json or None) if art else None


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


def comment_add(
    project_id: str,
    chapter: int,
    body: str,
    quote: str = "",
    from_pos: Optional[int] = None,
    to_pos: Optional[int] = None,
    anchor_status: str = "ok",
    persona: str = "author",
) -> Comment:
    persona = (persona or "author").strip().lower()
    if persona not in ("author", "editor", "beta"):
        persona = "author"
    with _session() as s:
        c = Comment(
            project_id=project_id,
            chapter=chapter,
            body=body,
            quote=quote,
            from_pos=from_pos,
            to_pos=to_pos,
            anchor_status=anchor_status,
            persona=persona,
        )
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


# --------------------------------------------------------------------------- media

def media_list(project_id: str, kind: Optional[str] = None) -> list[Media]:
    with _session() as s:
        q = select(Media).where(Media.project_id == project_id)
        if kind:
            q = q.where(Media.kind == kind)
        rows = s.exec(q.order_by(Media.created_at.desc())).all()
        return list(rows)


def media_by_sha(project_id: str, sha: str) -> Optional[Media]:
    with _session() as s:
        return s.exec(
            select(Media).where(Media.project_id == project_id, Media.sha == sha)
        ).first()


def media_add(project_id: str, sha: str, ext: str, filename: str, content_type: str,
              size: int, width: int, height: int, kind: str, alt: str = "") -> Media:
    """Insert, or return the existing row for identical bytes.

    Content-addressing makes re-upload idempotent: the same image in the same
    project is one row and one blob, however many times it is dropped in."""
    existing = media_by_sha(project_id, sha)
    if existing is not None:
        return existing
    with _session() as s:
        m = Media(
            project_id=project_id, sha=sha, ext=ext, filename=filename,
            content_type=content_type, size=size, width=width, height=height,
            kind=kind, alt=alt,
        )
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


def media_get(project_id: str, media_id: str) -> Optional[Media]:
    with _session() as s:
        m = s.get(Media, media_id)
        if m is None or m.project_id != project_id:
            return None
        return m


def media_update(
    project_id: str,
    media_id: str,
    *,
    alt: Optional[str] = None,
    kind: Optional[str] = None,
) -> Optional[Media]:
    with _session() as s:
        m = s.get(Media, media_id)
        if m is None or m.project_id != project_id:
            return None
        if alt is not None:
            m.alt = alt
        if kind is not None and kind.strip():
            m.kind = kind.strip()
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


def media_delete(project_id: str, media_id: str) -> Optional[Media]:
    """Remove the row and hand it back so the caller can drop the blob."""
    with _session() as s:
        m = s.get(Media, media_id)
        if not m or m.project_id != project_id:
            return None
        s.delete(m)
        s.commit()
        return m


# --------------------------------------------------------------------------- tenancy

def workspace_get(workspace_id: str) -> Optional[Workspace]:
    with _session() as s:
        return s.get(Workspace, workspace_id)


def workspace_create(id: str, name: str, slug: str) -> Workspace:
    with _session() as s:
        ws = Workspace(id=id, name=name, slug=slug)
        s.add(ws)
        s.commit()
        s.refresh(ws)
        return ws


def workspaces_list() -> list[Workspace]:
    with _session() as s:
        return list(s.exec(select(Workspace).order_by(Workspace.created_at)).all())


def user_create(email: str, display_name: str = "") -> User:
    with _session() as s:
        u = User(email=email, display_name=display_name)
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


def user_by_email(email: str) -> Optional[User]:
    with _session() as s:
        return s.exec(select(User).where(User.email == email)).first()


def membership_add(user_id: str, workspace_id: str, role: str = "owner") -> Membership:
    with _session() as s:
        existing = s.exec(
            select(Membership).where(
                Membership.user_id == user_id, Membership.workspace_id == workspace_id
            )
        ).first()
        if existing is not None:
            existing.role = role
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing
        m = Membership(user_id=user_id, workspace_id=workspace_id, role=role)
        s.add(m)
        s.commit()
        s.refresh(m)
        return m


def membership_get(user_id: str, workspace_id: str) -> Optional[Membership]:
    with _session() as s:
        return s.exec(
            select(Membership).where(
                Membership.user_id == user_id, Membership.workspace_id == workspace_id
            )
        ).first()


def project_claim(project_id: str, workspace_id: str) -> ProjectOwnership:
    """Record which workspace owns a project directory (idempotent)."""
    with _session() as s:
        row = s.get(ProjectOwnership, project_id)
        if row is None:
            row = ProjectOwnership(project_id=project_id, workspace_id=workspace_id)
        else:
            row.workspace_id = workspace_id
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def project_workspace(project_id: str) -> Optional[str]:
    with _session() as s:
        row = s.get(ProjectOwnership, project_id)
        return row.workspace_id if row else None


def projects_for_workspace(workspace_id: str) -> list[str]:
    with _session() as s:
        rows = s.exec(
            select(ProjectOwnership).where(ProjectOwnership.workspace_id == workspace_id)
        ).all()
        return [r.project_id for r in rows]


def _clear_all() -> None:
    """Test helper wipe every table."""
    with _session() as s:
        for model in (Artifact, Snapshot, Comment, Media, Chapter, Project,
                      AuthSession, Membership, ProjectOwnership, User, Workspace):
            s.exec(delete(model))
        s.commit()
