"""Tests for plot description generator parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from plot_generator import collect_bible_supporting_context, parse_plot_thread_update
from state_manager import StoryState, initialize_project


def test_parse_plot_thread_update_block():
    raw = """
Some analysis here.

[PLOT_THREAD_UPDATE]
Description: Jordan uncovers museum secrets while investigating a theft.
Bible_Suggestions:
- Theme of truth vs loyalty from the story bible
- Coastal Maine setting atmosphere
[/PLOT_THREAD_UPDATE]
"""
    parsed = parse_plot_thread_update(raw)
    assert "Jordan uncovers" in parsed["description"]
    assert len(parsed["bible_suggestions"]) == 2


def test_collect_bible_supporting_context(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.update_story_bible("themes", ["grief", "identity"])
    state.update_story_bible("tone", "literary suspense")
    ctx = collect_bible_supporting_context(state)
    assert "grief" in ctx
    assert "literary suspense" in ctx
    assert "Themes" in ctx
