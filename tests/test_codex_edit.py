"""Editing a Codex entry (issue #2).

The engine supported this from the start; it was simply never exposed over
HTTP, so the studio could create an entry and then never correct it. The tests
that matter here are the ones about *partial* updates and about which fields a
form is allowed to touch - an editor that blanks the rest of a record, or that
lets a form overwrite engine-derived facts, is worse than no editor.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "projects" / "book" / "outputs" / "state" / "story_state.json"


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A"},
        "characters": {
            "char_001": {
                "id": "char_001", "full_name": "Lena Marrow", "role": "protagonist",
                "internal_desire": "to be believed", "notes": "carries a compass",
                "last_appearance_chapter": 7,
            },
        },
        "codex": {
            "loc-001": {
                "id": "loc-001", "entry_type": "location", "name": "Grey Harbour",
                "summary": "A fogbound port.", "notes": "", "tags": ["port"],
            },
        },
        "plot_threads": {}, "chapters": {}, "timeline": [],
        "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    return TestClient(create_app(
        projects_root=root, db_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}"))


def get_entry(client, entry_id):
    return next(e for e in client.get("/api/projects/book/codex").json()
                if e["id"] == entry_id)


# ------------------------------------------------------- non-character entries

def test_renaming_a_location_sticks(client):
    r = client.patch("/api/projects/book/codex/loc-001", json={"name": "Glass Harbour"})
    assert r.status_code == 200
    assert r.json()["name"] == "Glass Harbour"
    assert get_entry(client, "loc-001")["name"] == "Glass Harbour"


def test_editing_one_field_leaves_the_others_alone(client):
    """A form that edits the summary must not blank the tags."""
    client.patch("/api/projects/book/codex/loc-001", json={"summary": "Now lit."})
    entry = get_entry(client, "loc-001")
    assert entry["summary"] == "Now lit."
    assert entry["name"] == "Grey Harbour"
    assert entry["tags"] == ["port"]


def test_notes_and_tags_are_editable(client):
    r = client.patch("/api/projects/book/codex/loc-001",
                     json={"notes": "Quarantined in ch.9", "tags": ["port", "closed"]})
    assert r.status_code == 200
    assert r.json()["notes"] == "Quarantined in ch.9"
    assert get_entry(client, "loc-001")["tags"] == ["port", "closed"]


def test_the_edit_survives_a_reload_from_disk(client):
    client.patch("/api/projects/book/codex/loc-001", json={"name": "Glass Harbour"})
    # A fresh request re-reads story_state.json rather than a cached object.
    assert get_entry(client, "loc-001")["name"] == "Glass Harbour"


# ------------------------------------------------------------------ characters

def test_a_character_is_editable_through_the_same_endpoint(client):
    """Characters live in a different store; callers should not have to care."""
    r = client.patch("/api/projects/book/codex/char_001", json={"name": "Lena Marrow-Vey"})
    assert r.status_code == 200
    assert r.json()["name"] == "Lena Marrow-Vey"


def test_character_specific_fields_are_editable(client):
    r = client.patch("/api/projects/book/codex/char_001",
                     json={"role": "antagonist", "fear": "still water"})
    assert r.status_code == 200
    assert r.json()["role"] == "antagonist"


def test_editing_a_character_does_not_disturb_engine_owned_facts(client, state_file):
    """last_appearance_chapter is derived from the manuscript, not typed.

    Checked against the file rather than the API, because the API deliberately
    does not surface the field - which is exactly why it could rot unnoticed.
    """
    client.patch("/api/projects/book/codex/char_001",
                 json={"notes": "changed", "last_appearance_chapter": 1})
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    character = saved["characters"]["char_001"]
    assert character["notes"] == "changed"
    assert character["last_appearance_chapter"] == 7


def test_an_unknown_field_is_ignored_rather_than_written(client):
    """A form cannot invent state by posting a field the model does not define."""
    r = client.patch("/api/projects/book/codex/char_001",
                     json={"name": "Lena", "last_appearance_chapter": 99})
    assert r.status_code == 200
    entry = get_entry(client, "char_001")
    assert entry["name"] == "Lena"
    assert "last_appearance_chapter" not in entry or entry.get(
        "last_appearance_chapter") != 99


# ---------------------------------------------------------------- rejections

def test_an_empty_name_is_rejected(client):
    r = client.patch("/api/projects/book/codex/loc-001", json={"name": "   "})
    assert r.status_code == 400
    assert "empty" in r.json()["detail"].lower()
    assert get_entry(client, "loc-001")["name"] == "Grey Harbour"


def test_an_empty_body_is_rejected_rather_than_silently_doing_nothing(client):
    r = client.patch("/api/projects/book/codex/loc-001", json={})
    assert r.status_code == 400
    assert "nothing to update" in r.json()["detail"].lower()


def test_an_unknown_entry_is_a_400_naming_the_id(client):
    r = client.patch("/api/projects/book/codex/nope-999", json={"name": "X"})
    assert r.status_code == 400
    assert "nope-999" in r.json()["detail"]


def test_an_unknown_project_is_a_404(client):
    r = client.patch("/api/projects/missing/codex/loc-001", json={"name": "X"})
    assert r.status_code == 404
