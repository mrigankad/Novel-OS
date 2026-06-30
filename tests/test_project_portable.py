"""Tests for portable project export/import."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from project_portable import build_package_bytes, import_package_bytes  # noqa: E402
from state_manager import Character, StoryState, initialize_project  # noqa: E402


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


@pytest.fixture
def project(tmp_path):
    initialize_project(str(tmp_path), "Portable Tale", "Fantasy")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_a", full_name="Alice", role="protagonist"))
    state.save_state()
    (tmp_path / "outputs" / "story_bible.md").write_text("# Bible\n", encoding="utf-8")
    return tmp_path


def test_build_and_import_package(project, tmp_path):
    db_export = {
        "version": 1,
        "project_id": "old-id",
        "project": {"id": "old-id", "title": "Portable Tale", "genre": "Fantasy",
                    "author": "", "status": "in_progress", "updated_at": ""},
        "chapters": [],
        "artifacts": [],
        "snapshots": [],
        "comments": [],
    }
    blob = build_package_bytes(
        project, db_export, project_id="old-id", title="Portable Tale",
    )
    assert blob[:2] == b"PK"

    imported: list[tuple[str, dict]] = []

    def import_db(new_id: str, data: dict) -> None:
        imported.append((new_id, data))

    def sync(new_id: str) -> None:
        pass

    dest = tmp_path / "library"
    new_id, title = import_package_bytes(
        dest,
        blob,
        import_db=import_db,
        sync_artifacts=sync,
        slugify=_slugify,
    )
    assert title == "Portable Tale"
    assert new_id == "portable-tale"
    assert (dest / new_id / "outputs" / "state" / "story_state.json").exists()
    state = StoryState(str(dest / new_id))
    assert state.get_character_by_name("Alice") is not None
    assert imported[0][0] == new_id
    assert imported[0][1]["project_id"] == "old-id"
