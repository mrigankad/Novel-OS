"""Saved collections (keyword searches) API."""

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    return TestClient(create_app(
        projects_root=projects,
        db_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        media_root=tmp_path / "media",
    ))


def test_collections_crud_and_results(tmp_path):
    client = _client(tmp_path)
    pid = client.post("/api/projects", json={
        "title": "Harbor", "genre": "Literary", "author": "Ada",
    }).json()["id"]
    client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "character", "name": "Lena Marrow", "role": "protagonist",
    })
    client.post(f"/api/projects/{pid}/codex", json={
        "entry_type": "location", "name": "Glass Harbor", "summary": "Fogbound",
    })

    assert client.get(f"/api/projects/{pid}/collections").json() == []

    created = client.post(f"/api/projects/{pid}/collections", json={
        "name": "Harbor cast", "query": "lena",
    })
    assert created.status_code == 201, created.text
    cols = created.json()
    assert len(cols) == 1
    assert cols[0]["query"] == "lena"
    cid = cols[0]["id"]

    results = client.get(f"/api/projects/{pid}/collections/{cid}/results").json()
    assert any("Lena" in h["label"] for h in results)

    filtered = client.post(f"/api/projects/{pid}/collections", json={
        "name": "Places", "query": "harbor", "kinds": ["location"],
    }).json()
    place_id = next(c["id"] for c in filtered if c["name"] == "Places")
    place_hits = client.get(f"/api/projects/{pid}/collections/{place_id}/results").json()
    assert place_hits
    assert all(h["kind"] == "location" for h in place_hits)

    assert client.delete(f"/api/projects/{pid}/collections/{cid}").status_code == 204
    left = client.get(f"/api/projects/{pid}/collections").json()
    assert all(c["id"] != cid for c in left)


def test_collection_rejects_short_query(tmp_path):
    client = _client(tmp_path)
    pid = client.post("/api/projects", json={
        "title": "X", "genre": "Drama", "author": "A",
    }).json()["id"]
    bad = client.post(f"/api/projects/{pid}/collections", json={"query": "a"})
    assert bad.status_code == 400
