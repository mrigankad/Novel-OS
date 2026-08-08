"""Create project with multi-genre + optional premise."""

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    return TestClient(create_app(
        projects_root=projects,
        db_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
    ))


def test_create_with_genres_and_premise(tmp_path):
    client = _client(tmp_path)
    resp = client.post("/api/projects", json={
        "title": "Saltlight",
        "author": "Ada",
        "genres": ["Romance", "Fantasy"],
        "premise": "A cartographer maps a city that redraws itself every dawn.",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["genre"] == "Romance · Fantasy"
    assert body["genres"] == ["Romance", "Fantasy"]
    assert "cartographer" in body["premise"]

    detail = client.get(f"/api/projects/{body['id']}").json()
    assert detail["genres"] == ["Romance", "Fantasy"]
    assert "cartographer" in detail["premise"]

    patched = client.patch(f"/api/projects/{body['id']}", json={
        "genres": ["Romance", "Fantasy", "Mystery"],
        "premise": "Updated brief.",
    }).json()
    assert patched["genre"] == "Romance · Fantasy · Mystery"
    assert patched["premise"] == "Updated brief."


def test_create_legacy_genre_string_still_works(tmp_path):
    client = _client(tmp_path)
    resp = client.post("/api/projects", json={
        "title": "Old Path", "genre": "Thriller", "author": "Bea",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["genre"] == "Thriller"
    assert "Thriller" in body["genres"]
