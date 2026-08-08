"""Project / session word targets (PLAN.md P4.4)."""

from fastapi.testclient import TestClient

from api.main import create_app


def test_update_word_targets(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    client = TestClient(create_app(
        projects_root=projects,
        db_url=f"sqlite:///{tmp_path / 't.db'}",
    ))
    created = client.post("/api/projects", json={
        "title": "Targets", "genre": "Drama", "author": "Ada",
    }).json()
    pid = created["id"]

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["target_word_count"] == 80000
    assert detail["session_word_target"] == 1000

    updated = client.patch(f"/api/projects/{pid}", json={
        "target_word_count": 90000,
        "session_word_target": 1500,
    }).json()
    assert updated["target_word_count"] == 90000
    assert updated["session_word_target"] == 1500

    again = client.get(f"/api/projects/{pid}").json()
    assert again["target_word_count"] == 90000
    assert again["session_word_target"] == 1500

    listed = client.get("/api/projects").json()
    row = next(p for p in listed if p["id"] == pid)
    assert row["target_word_count"] == 90000
