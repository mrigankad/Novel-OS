"""DB dialect helpers — SQLite locally, Postgres-ready URL later."""

from api.db import _connect_args_for, configure
from api import db
from sqlmodel import Session, select


def test_connect_args_sqlite_only():
    assert _connect_args_for("sqlite:///./novel_os.db") == {"check_same_thread": False}
    assert _connect_args_for("sqlite:////tmp/x.db") == {"check_same_thread": False}
    assert _connect_args_for("postgresql+psycopg://u:p@localhost:5432/novel_os") == {}
    assert _connect_args_for("postgresql://u:p@h/db") == {}


def test_configure_sqlite_roundtrip(tmp_path):
    url = f"sqlite:///{(tmp_path / 'dialect.db').as_posix()}"
    configure(url)
    from api.db import Project

    with Session(db._engine) as session:
        session.add(Project(id="demo", title="Demo", genre="Drama", author="Ada"))
        session.commit()
        row = session.exec(select(Project).where(Project.id == "demo")).one()
        assert row.title == "Demo"
