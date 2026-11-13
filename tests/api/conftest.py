"""Fresh SQLite database per test, and a TestClient on the real app."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("NOVEL_OS_DATABASE_URL", raising=False)
    from server import db
    db.reset_engine()
    from server.main import create_app
    with TestClient(create_app()) as c:
        yield c
    db.reset_engine()


@pytest.fixture
def project(client):
    return client.post("/api/projects", json={"title": "The Glass Orchard", "genre": "Literary"}).json()
