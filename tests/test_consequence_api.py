"""Unit tests for consequence preview helpers + API (mocked LLM)."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import ProjectService

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from consequence import (  # noqa: E402
    diff_findings, extract_predicted, extract_rewritten, splice_markdown,
)


def test_extract_rewritten_and_predicted():
    raw = """
[REWRITTEN]
She hesitated at the door.
[/REWRITTEN]
[SCRIBE_STATE_UPDATE]
Emotional_Shifts: Lena: wary
[/SCRIBE_STATE_UPDATE]
[PREDICTED_CONSEQUENCES]
- Mara may notice the hesitation later
- Trust erodes over the next three chapters
[/PREDICTED_CONSEQUENCES]
"""
    assert extract_rewritten(raw) == "She hesitated at the door."
    preds = extract_predicted(raw)
    assert len(preds) == 2
    assert "Mara" in preds[0]


def test_diff_findings():
    before = [{"category": "a", "message": "one", "chapter": 1, "entity_id": None}]
    after = before + [{"category": "b", "message": "two", "chapter": 1, "entity_id": "x"}]
    new = diff_findings(before, after)
    assert len(new) == 1
    assert new[0]["category"] == "b"


def test_splice_markdown():
    assert splice_markdown("aaa BBB ccc", "BBB", "XXX") == "aaa XXX ccc"
    with pytest.raises(ValueError):
        splice_markdown("aaa", "missing", "x")


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(projects_root=projects, db_url=f"sqlite:///{tmp_path / 't.db'}")
    return TestClient(app)


class _FakeLLM:
    def run_agent(self, _agent, _prompt):
        return """
[REWRITTEN]
Ilse almost dropped the red ledger.
[/REWRITTEN]
[SCRIBE_STATE_UPDATE]
Characters_Present: Ilse
Emotional_Shifts: Ilse: startled
Key_Events: Nearly drops the ledger
[/SCRIBE_STATE_UPDATE]
[PREDICTED_CONSEQUENCES]
- Someone in the hallway may have heard the thump
[/PREDICTED_CONSEQUENCES]
"""


class _FakeOrch:
    def _get_llm(self):
        return _FakeLLM()


def test_consequence_preview_and_accept(tmp_path, monkeypatch):
    client = _client(tmp_path)
    created = client.post("/api/projects", json={
        "title": "Harbor", "genre": "Mystery", "author": "Ada",
    }).json()
    pid = created["id"]

    # Seed chapter 1 via sample-like state: create_chapter through plan or empty write
    from state_manager import StoryState, Character, ChapterState
    root = tmp_path / "projects" / pid
    s = StoryState(str(root))
    s.add_character(Character(id="char_001", full_name="Ilse", role="protagonist"))
    s.chapters[1] = ChapterState(number=1, title="One", status="drafted", pov_character="Ilse")
    s.save_state()

    monkeypatch.setattr("api.services.build_orchestrator", lambda _dir: _FakeOrch())

    doc = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": "Ilse held the red ledger carefully."}],
        }],
    }
    put = client.put(f"/api/projects/{pid}/chapters/1/final/doc", json={"doc": doc})
    assert put.status_code == 200, put.text

    ProjectService._consequence_previews.clear()
    prev = client.post(
        f"/api/projects/{pid}/chapters/1/consequence/preview",
        json={
            "selection": "Ilse held the red ledger carefully.",
            "instruction": "She almost drops it",
            "before_context": "",
            "after_context": "",
        },
    )
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert "almost dropped" in body["rewritten"].lower()
    assert body["preview_id"]
    assert any("hallway" in p["message"] for p in body["predicted"])

    new_doc = {
        "type": "doc",
        "content": [{
            "type": "paragraph",
            "content": [{"type": "text", "text": body["rewritten"]}],
        }],
    }
    acc = client.post(
        f"/api/projects/{pid}/chapters/1/consequence/accept",
        json={
            "preview_id": body["preview_id"],
            "rewritten": body["rewritten"],
            "doc": new_doc,
            "state_delta": body["state_delta"],
        },
    )
    assert acc.status_code == 200, acc.text
    out = acc.json()
    assert "almost dropped" in out["final"]["markdown"].lower()
    # preview consumed
    again = client.post(
        f"/api/projects/{pid}/chapters/1/consequence/accept",
        json={
            "preview_id": body["preview_id"],
            "rewritten": body["rewritten"],
            "doc": new_doc,
            "state_delta": {},
        },
    )
    assert again.status_code == 400
