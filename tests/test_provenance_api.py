"""P3.2 pipeline provenance + stage diff."""

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


def test_stages_include_provenance_and_diff(tmp_path):
    client, projects = _client(tmp_path)
    created = client.post("/api/projects", json={
        "title": "Signal Path", "genre": "Thriller", "author": "Ada",
    }).json()
    pid = created["id"]

    from state_manager import StoryState, ChapterState
    root = projects / pid
    s = StoryState(str(root))
    s.chapters[1] = ChapterState(number=1, title="One", status="drafted")
    s.save_state()

    man = root / "outputs" / "manuscript"
    man.mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "chapter_001_outline.md").write_text(
        "Beat one.\nBeat two.\n", encoding="utf-8",
    )
    (man / "chapter_001_draft.md").write_text(
        "Beat one.\nShe opened the door.\nBeat two.\n", encoding="utf-8",
    )
    (man / "chapter_001_revised.md").write_text(
        "Beat one.\nShe eased the door open.\nA hinge complained.\n", encoding="utf-8",
    )

    db.upsert_artifact(
        pid, 1, "draft",
        (man / "chapter_001_draft.md").read_text(encoding="utf-8"),
        produced_by_agent="scribe",
        produced_by_model="claude:test",
    )
    db.upsert_artifact(
        pid, 1, "revised",
        (man / "chapter_001_revised.md").read_text(encoding="utf-8"),
        produced_by_agent="editor",
        produced_by_model="claude:test",
    )

    stages = client.get(f"/api/projects/{pid}/chapters/1/stages").json()
    assert stages["draft"]
    assert stages["provenance"]["draft"]["produced_by_agent"] == "scribe"
    assert "claude" in stages["provenance"]["draft"]["produced_by_model"]

    diff = client.get(
        f"/api/projects/{pid}/chapters/1/stages/diff",
        params={"from_stage": "draft", "to_stage": "revised"},
    ).json()
    assert diff["from_stage"] == "draft"
    assert diff["to_stage"] == "revised"
    assert diff["summary"]
    assert any("hinge" in ln.lower() for ln in diff["added_lines"]) or diff["to_words"] != diff["from_words"]
