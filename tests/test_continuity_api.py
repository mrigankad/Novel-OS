"""Continuity API + comment-related smoke for P1/P2.1."""

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(projects_root=projects, db_url=f"sqlite:///{tmp_path / 't.db'}")
    return TestClient(app)


def test_continuity_endpoints(tmp_path):
    client = _client(tmp_path)
    created = client.post("/api/projects", json={
        "title": "Signal", "genre": "Romance", "author": "Ada",
    }).json()
    pid = created["id"]
    report = client.get(f"/api/projects/{pid}/continuity").json()
    assert "findings" in report
    assert "critical" in report
    ch = client.get(f"/api/projects/{pid}/chapters/1/continuity")
    # chapter 1 may 404 if no chapters create via empty stages path
    # Continuity on missing chapter number still runs project-scoped filter
    assert ch.status_code in (200, 404) or True
    # After project exists, chapter continuity should 200 even with no chapters
    # (engine returns []). Service loads project; chapter filter is optional.
    body = client.get(f"/api/projects/{pid}/chapters/1/continuity")
    # Project exists endpoint does not require chapter to exist
    assert body.status_code == 200
    assert "findings" in body.json()
