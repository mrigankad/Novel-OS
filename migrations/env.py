"""Alembic environment: migrates the Novel OS database described by server.models."""

from alembic import context
from sqlmodel import SQLModel

from server import models  # noqa: F401  (registers every table)
from server.db import engine

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(url=str(engine().url), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection")
    if connectable is not None:
        _run(connectable)
        return
    with engine().connect() as connection:
        _run(connection)


def _run(connection) -> None:  # noqa: ANN001
    # render_as_batch: SQLite can't ALTER most things; batch mode rebuilds tables safely.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
