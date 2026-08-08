"""P3.3 review workflow: accept/reject AI stages; agents never write Final."""

from fastapi.testclient import TestClient

from api.main import create_app
from api import db


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(
        projects_root=projects,
        db_url=f"sqlite:///{tmp_path / 't.db'}",
    )
    return TestClient(app), projects


def _seed_chapter(client, projects, draft="Draft body.\n", revised=None):
    created = client.post("/api/projects", json={
        "title": "Review Path", "genre": "Drama", "author": "Ada",
    }).json()
    pid = created["id"]

    from state_manager import StoryState, ChapterState
    root = projects / pid
    s = StoryState(str(root))
    s.chapters[1] = ChapterState(number=1, title="One", status="drafted")
    s.save_state()

    man = root / "outputs" / "manuscript"
    man.mkdir(parents=True, exist_ok=True)
    (man / "chapter_001_draft.md").write_text(draft, encoding="utf-8")
    db.upsert_artifact(
        pid, 1, "draft", draft,
        produced_by_agent="scribe",
        produced_by_model="claude:test",
    )
    if revised is not None:
        (man / "chapter_001_revised.md").write_text(revised, encoding="utf-8")
        db.upsert_artifact(
            pid, 1, "revised", revised,
            produced_by_agent="editor",
            produced_by_model="claude:test",
        )
    return pid


def test_accept_draft_stamps_review_and_promotes_final(tmp_path):
    client, projects = _client(tmp_path)
    pid = _seed_chapter(client, projects, draft="She opened the door.\n")

    resp = client.post(
        f"/api/projects/{pid}/chapters/1/stages/draft/review",
        json={"decision": "accept"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "accept"
    assert body["reviewed_by"] == "author"
    assert body["promoted_final"] is True

    stages = client.get(f"/api/projects/{pid}/chapters/1/stages").json()
    assert stages["final"]
    assert "door" in stages["final"].lower()
    assert stages["provenance"]["draft"]["reviewed_by"] == "author"


def test_reject_draft_leaves_final_untouched(tmp_path):
    client, projects = _client(tmp_path)
    pid = _seed_chapter(client, projects, draft="Unwanted draft.\n")

    resp = client.post(
        f"/api/projects/{pid}/chapters/1/stages/draft/review",
        json={"decision": "reject"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "reject"
    assert body["promoted_final"] is False

    stages = client.get(f"/api/projects/{pid}/chapters/1/stages").json()
    assert stages["final"] is None
    assert not (stages["provenance"]["draft"].get("reviewed_by") or "")


def test_promote_blocked_without_review_when_provenance_exists(tmp_path):
    client, projects = _client(tmp_path)
    pid = _seed_chapter(client, projects, draft="Gate me.\n")

    blocked = client.post(f"/api/projects/{pid}/chapters/1/final/promote")
    assert blocked.status_code == 400

    forced = client.post(f"/api/projects/{pid}/chapters/1/final/promote?force=true")
    assert forced.status_code == 200
    assert "Gate" in forced.json()["final"]


def test_accept_prefers_revised_over_draft(tmp_path):
    client, projects = _client(tmp_path)
    pid = _seed_chapter(
        client, projects,
        draft="Old draft.\n",
        revised="Polished revised line.\n",
    )

    resp = client.post(
        f"/api/projects/{pid}/chapters/1/stages/revised/review",
        json={"decision": "accept"},
    )
    assert resp.status_code == 200
    stages = client.get(f"/api/projects/{pid}/chapters/1/stages").json()
    assert "Polished" in stages["final"]
    assert stages["provenance"]["revised"]["reviewed_by"] == "author"


def test_review_rejects_outline_and_bad_decision(tmp_path):
    client, projects = _client(tmp_path)
    pid = _seed_chapter(client, projects)

    assert client.post(
        f"/api/projects/{pid}/chapters/1/stages/outline/review",
        json={"decision": "accept"},
    ).status_code == 400

    assert client.post(
        f"/api/projects/{pid}/chapters/1/stages/draft/review",
        json={"decision": "maybe"},
    ).status_code == 400
