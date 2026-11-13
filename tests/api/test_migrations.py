"""Schema is managed by Alembic (migrations/)."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import SQLModel


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("NOVEL_OS_DATABASE_URL", raising=False)
    from server import db
    db.reset_engine()
    return db


def test_fresh_database_is_at_head(tmp_path, monkeypatch):
    db = _fresh(tmp_path, monkeypatch)
    db.init_db()
    with db.engine().connect() as c:
        version = c.execute(text("select version_num from alembic_version")).scalar()
    assert version
    assert "chapter" in inspect(db.engine()).get_table_names()
    db.reset_engine()


def test_pre_migration_database_is_stamped_not_recreated(tmp_path, monkeypatch):
    db = _fresh(tmp_path, monkeypatch)
    from server import models  # noqa: F401
    SQLModel.metadata.create_all(db.engine())  # how Novel OS 2.0 dev databases were made
    with db.engine().begin() as c:
        c.execute(text("insert into project (id, title, author, genre, premise, bible, target_words, status, "
                       "created_at, updated_at) values ('p1', 'Kept', '', '', '', '{}', 1, 'drafting', "
                       "'2026-01-01', '2026-01-01')"))
    db.init_db()
    with db.engine().connect() as c:
        assert c.execute(text("select title from project where id='p1'")).scalar() == "Kept"
        assert c.execute(text("select version_num from alembic_version")).scalar()
    db.reset_engine()


def test_models_match_migrations(tmp_path, monkeypatch):
    """If this fails you changed a model: run
    `python -m alembic revision --autogenerate -m "<what changed>"` and commit the file."""
    db = _fresh(tmp_path, monkeypatch)
    db.init_db()
    from server import models  # noqa: F401
    with db.engine().connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), SQLModel.metadata)
    assert diff == [], diff
    db.reset_engine()
