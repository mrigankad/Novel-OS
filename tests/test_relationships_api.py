"""Relationship edges API (context menu / chart system)."""

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    return TestClient(create_app(
        projects_root=projects,
        db_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
    ))


def test_relationships_crud(tmp_path):
    client = _client(tmp_path)
    pid = client.post("/api/projects", json={
        "title": "Web", "genre": "Drama", "author": "Ada",
    }).json()["id"]

    client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "character", "name": "Lena", "role": "protagonist",
    })
    client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "character", "name": "Mara", "role": "supporting",
    })
    chars = client.get(f"/api/projects/{pid}/codex?entry_type=character").json()
    a = next(c for c in chars if c["name"] == "Lena")
    b = next(c for c in chars if c["name"] == "Mara")

    created = client.post(f"/api/projects/{pid}/relationships", json={
        "source_id": a["id"], "target_id": b["id"], "label": "rivals",
    })
    assert created.status_code == 201, created.text
    edges = created.json()
    assert len(edges) == 1
    assert edges[0]["label"] == "rivals"
    assert edges[0]["source_name"] == "Lena"

    listed = client.get(f"/api/projects/{pid}/relationships").json()
    assert len(listed) == 1

    # Idempotent update of same undirected pair
    again = client.post(f"/api/projects/{pid}/relationships", json={
        "source_id": b["id"], "target_id": a["id"], "label": "uneasy allies",
    })
    assert again.status_code == 201
    assert len(again.json()) == 1
    assert again.json()[0]["label"] == "uneasy allies"

    edge_id = again.json()[0]["id"]
    assert client.delete(f"/api/projects/{pid}/relationships/{edge_id}").status_code == 204
    assert client.get(f"/api/projects/{pid}/relationships").json() == []
