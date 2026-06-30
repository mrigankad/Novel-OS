"""Tests for entity deduplication."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from entity_dedup import (
    character_match_score,
    filter_stale_entity_groups,
    find_character_duplicate_groups,
    find_matching_character,
    merge_characters,
    register_name_as_alias,
    scan_duplicates,
)
from state_manager import Character, PlotThread, StoryState, initialize_project


def test_character_match_nora_variants():
    assert character_match_score("Nora Blake", "Nora") >= 0.88
    assert character_match_score("Nina Blake (infant)", "Nina") >= 0.88


def test_find_and_merge_character_duplicates(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_nora_blake", full_name="Nora Blake", role="supporting"))
    state.add_character(Character(id="char_nora", full_name="Nora", role="supporting"))
    state.add_character(Character(id="char_jordan", full_name="Jordan Lee", role="protagonist"))
    groups = find_character_duplicate_groups(state, min_score=0.85)
    assert len(groups) == 1
    assert len(groups[0].members) == 2
    log = merge_characters(state, groups[0].suggested_keep_id, ["char_nora"])
    assert len(log) == 1
    assert len(state.characters) == 2
    assert state.get_character_by_name("Nora Blake") is not None


def test_scan_duplicates_api_shape(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="a", full_name="Chris Webb", role="supporting"))
    state.add_character(Character(id="b", full_name="Jordan (formerly Chris)", role="supporting"))
    report = scan_duplicates(state)
    assert "characters" in report
    assert "plot_threads" in report


def test_character_alias_exact_match(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(
        id="char_jordan", full_name="Jordan Lee", role="protagonist",
        aliases=["Nickname", "Ms. Lee", "Mrs Quinn"],
    ))
    assert state.get_character_by_name("Nickname") is not None
    assert find_matching_character(state, "Mrs Quinn", min_score=0.85) == "char_jordan"


def test_merge_characters_preserves_aliases(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_jordan", full_name="Jordan Lee", role="protagonist"))
    state.add_character(Character(id="char_nick", full_name="Nickname", role="supporting", aliases=["Ms. Lee"]))
    merge_characters(state, "char_jordan", ["char_nick"])
    jordan = state.characters["char_jordan"]
    assert state.get_character_by_name("Nickname") == jordan
    assert state.get_character_by_name("Ms. Lee") == jordan
    assert "Nickname" in jordan.aliases


def test_register_name_as_alias_skips_canonical(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_jordan", full_name="Jordan Lee", role="protagonist"))
    assert register_name_as_alias(state, "char_jordan", "Jordan Lee") is False
    assert register_name_as_alias(state, "char_jordan", "Nickname") is True
    assert state.get_character_by_name("Nickname") is not None


def test_filter_stale_entity_groups_drops_missing_members(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_plot_thread(PlotThread(
        id="plot_a", name="Main quest", description="", thread_type="main",
    ))
    groups = [{
        "kind": "plot_thread",
        "confidence": 0.9,
        "reason": "AI",
        "suggested_keep_id": "plot_a",
        "members": [
            {"id": "plot_a", "label": "Main quest", "thread_type": "main"},
            {"id": "plot_b", "label": "Deleted thread", "thread_type": "main"},
        ],
    }]
    filtered = filter_stale_entity_groups(state, groups, "plot_thread")
    assert filtered == []
