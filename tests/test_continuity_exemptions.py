"""Marking a continuity finding intentional (PLAN.md P2.1).

A checker cannot tell an unreliable narrator, deliberate foreshadowing, or a
character who lies from a real mistake. If a dismissal does not persist, the
panel re-raises the same non-error every run and the writer stops reading it -
which costs more than the check is worth.
"""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from api.main import create_app  # noqa: E402
from continuity_engine import Finding, drop_exempt, run_all  # noqa: E402
from state_manager import RelationshipEdge, StoryState  # noqa: E402


def _state(tmp_path):
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    return StoryState(str(root))


# ------------------------------------------------------------------ the key

def test_key_identifies_the_fact_not_the_wording():
    a = Finding(severity="warning", category="eye_colour", message="grey vs green",
                entity_id="char_001", chapter=3)
    b = Finding(severity="warning", category="eye_colour",
                message="totally reworded message", entity_id="char_001", chapter=11)
    assert a.key == b.key


def test_key_separates_different_entities():
    a = Finding(severity="warning", category="eye_colour", message="m", entity_id="c1")
    b = Finding(severity="warning", category="eye_colour", message="m", entity_id="c2")
    assert a.key != b.key


def test_key_is_serialised_for_the_client():
    f = Finding(severity="info", category="x", message="m", entity_id="e1")
    assert f.to_dict()["key"] == f.key


# --------------------------------------------------------------- filtering

def test_exempt_findings_are_dropped(tmp_path):
    s = _state(tmp_path)
    findings = [
        Finding(severity="warning", category="eye_colour", message="m", entity_id="c1"),
        Finding(severity="warning", category="timeline", message="m", entity_id="c1"),
    ]
    s.exempt_finding("eye_colour:c1", "She lies about her eyes")
    left = drop_exempt(s, findings)
    assert [f.category for f in left] == ["timeline"]


def test_run_all_honours_exemptions(tmp_path):
    """The filter lives in the engine, so the Guardian sees it too."""
    s = _state(tmp_path)
    s.relationships["rel-x"] = RelationshipEdge(
        id="rel-x", source_id="a", target_id="b", label="enemy")

    orphan = next(f for f in run_all(s) if f.category == "relationship_orphan")
    s.exempt_finding(orphan.key, "deliberate")
    assert not any(f.category == "relationship_orphan" for f in run_all(s))


def test_unexempting_brings_the_finding_back(tmp_path):
    s = _state(tmp_path)
    s.relationships["rel-x"] = RelationshipEdge(
        id="rel-x", source_id="a", target_id="b", label="enemy")
    key = next(f for f in run_all(s) if f.category == "relationship_orphan").key

    s.exempt_finding(key, "deliberate")
    assert s.unexempt_finding(key) is True
    assert any(f.category == "relationship_orphan" for f in run_all(s))


def test_unexempting_something_unknown_is_false(tmp_path):
    assert _state(tmp_path).unexempt_finding("nope:1") is False


def test_an_exemption_records_its_reason_and_time(tmp_path):
    s = _state(tmp_path)
    record = s.exempt_finding("eye_colour:c1", "She lies about her eyes")
    assert record["reason"] == "She lies about her eyes"
    assert record["at"]


def test_an_exemption_needs_a_key(tmp_path):
    with pytest.raises(ValueError):
        _state(tmp_path).exempt_finding("  ", "why")


def test_exemptions_survive_a_reload(tmp_path):
    """The whole feature is worthless if it does not persist."""
    s = _state(tmp_path)
    s.exempt_finding("eye_colour:c1", "She lies")

    reloaded = StoryState(str(tmp_path / "proj"))
    assert "eye_colour:c1" in reloaded.continuity_exemptions
    assert reloaded.continuity_exemptions["eye_colour:c1"]["reason"] == "She lies"


# --------------------------------------------------------------------- API

@pytest.fixture
def client(tmp_path):
    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A"},
        "characters": {}, "plot_threads": {},
        "relationships": {"rel-x": {
            "id": "rel-x", "source_id": "a", "target_id": "b", "label": "enemy"}},
        "chapters": {"1": {"number": 1, "title": "One", "status": "drafted"}},
        "timeline": [], "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    app = create_app(projects_root=root,
                     db_url=f"sqlite:///{(tmp_path / 'e.db').as_posix()}")
    return TestClient(app)


def _orphan_key(client):
    report = client.get("/api/projects/book/continuity").json()
    return next(f["key"] for f in report["findings"]
                if f["category"] == "relationship_orphan")


def test_findings_carry_a_key_over_the_wire(client):
    assert _orphan_key(client)


def test_exempting_removes_it_from_the_report(client):
    key = _orphan_key(client)
    r = client.post("/api/projects/book/continuity/exemptions",
                    json={"key": key, "reason": "deliberate"})
    assert r.status_code == 201
    assert r.json()["reason"] == "deliberate"

    report = client.get("/api/projects/book/continuity").json()
    assert not any(f["category"] == "relationship_orphan" for f in report["findings"])


def test_exemptions_are_listable_so_the_writer_can_review_them(client):
    key = _orphan_key(client)
    client.post("/api/projects/book/continuity/exemptions",
                json={"key": key, "reason": "deliberate"})

    body = client.get("/api/projects/book/continuity/exemptions").json()
    assert [e["key"] for e in body] == [key]
    assert body[0]["reason"] == "deliberate"


def test_deleting_an_exemption_restores_the_finding(client):
    key = _orphan_key(client)
    client.post("/api/projects/book/continuity/exemptions",
                json={"key": key, "reason": "deliberate"})

    assert client.delete(
        f"/api/projects/book/continuity/exemptions/{key}").status_code == 204
    assert _orphan_key(client) == key


def test_deleting_an_unknown_exemption_is_404(client):
    assert client.delete(
        "/api/projects/book/continuity/exemptions/nope:1").status_code == 404


def test_an_empty_key_is_rejected(client):
    r = client.post("/api/projects/book/continuity/exemptions",
                    json={"key": "  ", "reason": "x"})
    assert r.status_code == 400
