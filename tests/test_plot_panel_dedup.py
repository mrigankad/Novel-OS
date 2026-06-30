"""Tests for plot-panel subplot deduplication."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from entity_dedup import (
    auto_resolve_plot_panel_issues,
    find_plot_panel_issues,
    resolve_plot_panel_issue,
)
from state_manager import PlotThread, StoryState, initialize_project


def _add_plot(state: StoryState, tid: str, name: str, **kwargs) -> PlotThread:
    desc = kwargs.pop("description", name)
    thread_type = kwargs.pop("thread_type", "main")
    thread = PlotThread(id=tid, name=name, description=desc, thread_type=thread_type, **kwargs)
    state.add_plot_thread(thread)
    return thread


def test_duplicate_subplot_across_parents(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    _add_plot(state, "plot_main", "Main investigation arc", subplots=[])
    _add_plot(
        state, "plot_other", "Family secrets",
        subplots=["Hidden inheritance: protagonist learns the truth"],
    )
    _add_plot(
        state, "plot_dup", "Side cases",
        subplots=["Hidden inheritance: duplicate wording"],
    )
    issues = find_plot_panel_issues(state, min_score=0.78)
    kinds = {i.kind for i in issues}
    assert "duplicate_subplot_across" in kinds
    issue = next(i for i in issues if i.kind == "duplicate_subplot_across")
    log = resolve_plot_panel_issue(state, issue.issue_id, issues=issues)
    assert log
    remaining = find_plot_panel_issues(state)
    assert not any(i.kind == "duplicate_subplot_across" for i in remaining)


def test_thread_matches_subplot_on_other_parent(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    _add_plot(state, "plot_main", "Main arc", subplots=["Romance subplot: Maya and Leo"])
    _add_plot(
        state, "plot_orphan", "Romance subplot",
        description="Should nest under main",
        thread_type="subplot",
    )
    issues = find_plot_panel_issues(state, min_score=0.78)
    assert any(i.kind == "thread_under_wrong_parent" for i in issues)
    log = auto_resolve_plot_panel_issues(state, min_score=0.78)
    assert log
    assert "plot_orphan" not in state.plot_threads or any(
        "Romance subplot" in s for t in state.plot_threads.values() for s in t.subplots
    )


def test_duplicate_subplot_within_same_thread(tmp_path):
    initialize_project(str(tmp_path), "Test", "Fiction")
    state = StoryState(str(tmp_path))
    _add_plot(
        state, "plot_main", "Main",
        subplots=[
            "Heist planning: crew assembles",
            "Heist planning: the crew gathers",
        ],
    )
    issues = find_plot_panel_issues(state)
    assert any(i.kind == "duplicate_subplot_within" for i in issues)
    auto_resolve_plot_panel_issues(state, min_score=0.78)
    thread = state.plot_threads["plot_main"]
    assert len(thread.subplots) == 1
