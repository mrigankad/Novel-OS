"""Tests for parsing AI dedup JSON from local model output."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from entity_dedup import ai_suggest_duplicate_groups
from state_manager import PlotThread, StoryState, initialize_project, Character
from state_parser import parse_json_object


def test_parse_json_object_strips_thinking_tags():
    raw = """<think>long reasoning here</think>

{
  "character_groups": [],
  "plot_groups": []
}
"""
    data = parse_json_object(raw)
    assert data["plot_groups"] == []


def test_ai_suggest_duplicate_groups_with_thinking_wrapped_json(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_a", full_name="Nora Blake", role="supporting"))
    state.add_character(Character(id="char_b", full_name="Nora", role="supporting"))
    state.add_plot_thread(PlotThread(
        id="plot_a", name="Main quest", description="", thread_type="main",
    ))
    state.add_plot_thread(PlotThread(
        id="plot_b", name="Main Quest Arc", description="", thread_type="main",
    ))

    class MockLLM:
        def complete(self, system, prompt):
            return (
                "<think>thinking…</think>\n"
                + json.dumps({
                    "character_groups": [{
                        "keep_id": "char_a",
                        "merge_ids": ["char_b"],
                        "reason": "Same person",
                        "confidence": 0.95,
                    }],
                    "plot_groups": [{
                        "keep_id": "plot_a",
                        "merge_ids": ["plot_b"],
                        "reason": "Same thread",
                        "confidence": 0.9,
                    }],
                })
            )

    report = ai_suggest_duplicate_groups(state, MockLLM())
    assert len(report["characters"]) == 1
    assert len(report["plot_threads"]) == 1
    assert report["plot_threads"][0].suggested_keep_id == "plot_a"
