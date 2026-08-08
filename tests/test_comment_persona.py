"""Comment personas (author / editor / beta)."""

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(
        projects_root=projects,
        db_url=f"sqlite:///{tmp_path / 't.db'}",
    )
    return TestClient(app), projects


def test_comment_persona_round_trip(tmp_path):
    client, projects = _client(tmp_path)
    created = client.post("/api/projects", json={
        "title": "Notes", "genre": "Drama", "author": "Ada",
    }).json()
    pid = created["id"]

    from state_manager import StoryState, ChapterState
    root = projects / pid
    s = StoryState(str(root))
    s.chapters[1] = ChapterState(number=1, title="One", status="drafted")
    s.save_state()

    resp = client.post(
        f"/api/projects/{pid}/chapters/1/comments",
        json={"body": "Tighten the opening.", "persona": "editor"},
    )
    assert resp.status_code == 201
    assert resp.json()["persona"] == "editor"
    assert resp.json()["body"] == "Tighten the opening."

    listed = client.get(f"/api/projects/{pid}/chapters/1/comments").json()
    assert listed[0]["persona"] == "editor"

    bad = client.post(
        f"/api/projects/{pid}/chapters/1/comments",
        json={"body": "Fallback", "persona": "critic"},
    )
    assert bad.status_code == 201
    assert bad.json()["persona"] == "author"
