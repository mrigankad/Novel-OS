"""Codex proposal endpoint (PLAN.md P2.2).

The contract under test is that proposing never writes: importing a manuscript
must not silently populate the world model.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

CH1 = """
Lena Marrow stood at the rail. "You should go inside," said Mara.
Lena shook her head. Mara watched her, then went below.
"Suit yourself," Mara called back up the stairs.
Lena stayed until the lights of Grey Harbour disappeared.
Grey Harbour was behind them now. Grey Harbour always would be.
"""


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "manuscript").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A"},
        "characters": {}, "plot_threads": {},
        "chapters": {"1": {"number": 1, "title": "One", "status": "drafted"}},
        "timeline": [], "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    (proj / "outputs" / "manuscript" / "chapter_001_final.md").write_text(
        CH1, encoding="utf-8")
    app = create_app(projects_root=root,
                     db_url=f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    return TestClient(app)


def test_proposals_are_returned_from_the_manuscript(client):
    r = client.get("/api/projects/book/codex/proposals")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "Mara" in names
    assert "Grey Harbour" in names


def test_each_proposal_explains_itself(client):
    body = client.get("/api/projects/book/codex/proposals").json()
    mara = next(p for p in body if p["name"] == "Mara")
    assert mara["entry_type"] == "character"
    assert "speaks" in mara["evidence"]
    assert mara["chapters"] == [1]
    assert "Mara" in mara["excerpt"]


def test_proposing_does_not_write_to_the_world_model(client):
    """The whole point: extraction proposes, the human disposes."""
    client.get("/api/projects/book/codex/proposals")
    assert client.get("/api/projects/book/codex").json() == []


def test_accepted_names_stop_being_proposed(client):
    client.post("/api/projects/book/codex",
                json={"entry_type": "location", "name": "Grey Harbour"})
    names = [p["name"] for p in client.get("/api/projects/book/codex/proposals").json()]
    assert "Grey Harbour" not in names


def test_min_mentions_and_limit_are_honoured(client):
    body = client.get(
        "/api/projects/book/codex/proposals?min_mentions=1&limit=2").json()
    assert len(body) == 2


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nope/codex/proposals").status_code == 404


def test_a_project_with_no_prose_proposes_nothing(client, tmp_path):
    (tmp_path / "projects" / "book" / "outputs" / "manuscript"
     / "chapter_001_final.md").unlink()
    assert client.get("/api/projects/book/codex/proposals").json() == []
