"""Tests for project-level backup/restore."""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from project_backup import (  # noqa: E402
    create_named_backup,
    list_backups,
    quick_restore,
    quick_save,
    restore_named_backup,
)
from state_manager import Character, PlotThread, StoryState, initialize_project  # noqa: E402


@pytest.fixture
def project(tmp_path):
    initialize_project(str(tmp_path), "Test Novel", "Drama")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_a", full_name="Alice", role="protagonist", aliases=["A."]))
    state.add_plot_thread(
        PlotThread(
            id="plot_main",
            name="Main Arc",
            description="Primary storyline",
            thread_type="main",
            subplots=["Nested beat: vault job"],
        ),
    )
    state.story_bible["background_blocks"] = [
        {"label": "World notes", "summary": "Mirrored lobby", "extracted_at": "2026-01-01"},
    ]
    state.story_bible["themes"] = ["Loss and inheritance"]
    state.save_state()

    outputs = tmp_path / "outputs"
    (outputs / "story_bible.md").write_text("# Bible\n", encoding="utf-8")
    dedup = outputs / "dedup"
    dedup.mkdir(parents=True)
    (dedup / "suggestions.json").write_text(
        json.dumps({"characters": [{"kind": "character", "members": []}], "plot_threads": []}),
        encoding="utf-8",
    )
    (dedup / "bible_suggestions.json").write_text(
        json.dumps({"groups": [{"section": "themes", "members": []}]}),
        encoding="utf-8",
    )
    feedback = outputs / "feedback"
    feedback.mkdir(parents=True)
    (feedback / "character_generate_preview.json").write_text('{"prompt":"bio"}', encoding="utf-8")
    (feedback / "plot_generate_plot_main_preview.json").write_text('{"description":"x"}', encoding="utf-8")
    (feedback / "chapter_001_mine_bible_report.md").write_text("# mine report", encoding="utf-8")
    background = outputs / "background" / "reports"
    background.mkdir(parents=True)
    (background / "notes_report.md").write_text("# import report", encoding="utf-8")
    return tmp_path


def _db_export(project_id: str = "x") -> dict:
    return {
        "version": 1,
        "project_id": project_id,
        "project": None,
        "chapters": [],
        "artifacts": [],
        "snapshots": [],
        "comments": [],
    }


def test_named_backup_and_list(project):
    entry = create_named_backup(project, "Before edits", db_export=_db_export())
    assert entry["label"] == "Before edits"
    report = list_backups(project)
    assert len(report["named"]) == 1
    assert report["named"][0]["id"] == entry["id"]


def test_backup_archive_includes_extended_outputs(project):
    entry = create_named_backup(project, "Full state", db_export=_db_export())
    zip_path = project / "backups" / "named" / entry["filename"]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
    expected = {
        "db_export.json",
        "outputs/state/story_state.json",
        "outputs/dedup/suggestions.json",
        "outputs/dedup/bible_suggestions.json",
        "outputs/feedback/character_generate_preview.json",
        "outputs/feedback/plot_generate_plot_main_preview.json",
        "outputs/feedback/chapter_001_mine_bible_report.md",
        "outputs/background/reports/notes_report.md",
    }
    missing = expected - names
    assert not missing, f"Backup missing paths: {missing}"


def test_quick_save_and_restore_roundtrip(project):
    imported = []

    def import_db(data):
        imported.append(data)

    def sync():
        pass

    quick_save(project, db_export=_db_export())
    state = StoryState(str(project))
    state.add_character(Character(id="char_b", full_name="Bob", role="supporting"))
    state.save_state()

    quick_restore(project, db_export=_db_export(), import_db=import_db, sync_artifacts=sync)
    state2 = StoryState(str(project))
    assert state2.get_character_by_name("Bob") is None
    assert state2.get_character_by_name("Alice") is not None
    assert len(imported) == 1


def test_restore_preserves_dedup_and_bible_structures(project):
    entry = create_named_backup(project, "Snapshot", db_export=_db_export())
    state = StoryState(str(project))
    state.story_bible["themes"] = ["Changed after backup"]
    state.save_state()
    (project / "outputs" / "dedup" / "suggestions.json").write_text("{}", encoding="utf-8")

    restore_named_backup(
        project,
        entry["id"],
        import_db=lambda _data: None,
        sync_artifacts=lambda: None,
    )

    restored = StoryState(str(project))
    assert restored.story_bible["themes"] == ["Loss and inheritance"]
    assert restored.story_bible["background_blocks"][0]["label"] == "World notes"
    assert restored.plot_threads["plot_main"].subplots == ["Nested beat: vault job"]
    assert restored.get_character_by_name("Alice").aliases == ["A."]
    suggestions = json.loads(
        (project / "outputs" / "dedup" / "suggestions.json").read_text(encoding="utf-8"),
    )
    assert "characters" in suggestions
    bible_ai = json.loads(
        (project / "outputs" / "dedup" / "bible_suggestions.json").read_text(encoding="utf-8"),
    )
    assert bible_ai["groups"]
    assert (project / "outputs" / "feedback" / "character_generate_preview.json").exists()
