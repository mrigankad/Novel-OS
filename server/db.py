"""Database engine and sessions.

SQLite (WAL, foreign keys on) by default under ./data; any SQLAlchemy URL works
via NOVEL_OS_DATABASE_URL (e.g. postgresql+psycopg://user:pass@host/novel_os).
Tables come from server.models; schema changes go through Alembic (migrations/).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_engine = None


def engine():
    global _engine
    if _engine is None:
        url = settings().database_url
        is_sqlite = url.startswith("sqlite")
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if is_sqlite else {},
            pool_pre_ping=not is_sqlite,
        )
        if is_sqlite:
            @event.listens_for(_engine, "connect")
            def _pragmas(conn, _record):  # noqa: ANN001
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()
    return _engine


def reset_engine() -> None:
    """Tests: drop the cached engine after changing settings."""
    global _engine
    _engine = None
    settings.cache_clear()


def _alembic_config():
    from pathlib import Path

    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return cfg


def init_db() -> None:
    """Bring the schema to the latest migration.

    A database created before migrations existed (tables present, no
    alembic_version) is stamped at the baseline first, so nothing is lost.
    Falls back to create_all if Alembic isn't installed.
    """
    from . import models  # noqa: F401  (registers every table)

    try:
        from alembic import command
    except ImportError:  # pragma: no cover
        SQLModel.metadata.create_all(engine())
        return

    from sqlalchemy import inspect

    cfg = _alembic_config()
    tables = set(inspect(engine()).get_table_names())
    with engine().begin() as conn:
        cfg.attributes["connection"] = conn
        if tables and "alembic_version" not in tables:
            command.stamp(cfg, "f848e5e0e161")
        command.upgrade(cfg, "head")


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(engine()) as s:
        yield s


@contextmanager
def session_scope() -> Iterator[Session]:
    """For background jobs: commit on success, roll back on error."""
    with Session(engine()) as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
