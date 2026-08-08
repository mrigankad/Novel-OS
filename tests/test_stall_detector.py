"""Sagging-middle detection (design spec §4.3).

Middles are where books die, and the failure has a measurable shape: the
protagonist goes reactive and nothing changes for a stretch. These tests pin the
line between "a quiet chapter" and "the book has stalled", because a detector
that cries wolf is worse than no detector.
"""

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from continuity_engine import run_all  # noqa: E402
from stall_detector import (  # noqa: E402
    book_shape, chapter_activity, find_stalls,
)
from state_manager import ChapterState, PlotThread, StoryState  # noqa: E402


def _state(tmp_path):
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    return StoryState(str(root))


def _flat(n, pov="Lena", status="drafted"):
    return ChapterState(number=n, title=f"Ch {n}", pov_character=pov, status=status)


def _moving(n, pov="Lena"):
    return ChapterState(
        number=n, title=f"Ch {n}", pov_character=pov, status="drafted",
        plot_advances=["she decides to go"],
    )


# --------------------------------------------------------------- activity

def test_a_chapter_that_changes_nothing_is_flat(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    assert chapter_activity(s, 1).is_flat is True


def test_any_recorded_change_makes_a_chapter_not_flat(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _moving(1)
    a = chapter_activity(s, 1)
    assert a.is_flat is False
    assert a.movement == 1


def test_a_touched_thread_counts_as_movement(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    s.plot_threads["t1"] = PlotThread(
        id="t1", name="The debt", description="", thread_type="main",
        last_updated_chapter=1,
    )
    assert chapter_activity(s, 1).is_flat is False


def test_an_unwritten_chapter_is_never_flat(tmp_path):
    """A chapter that does not exist yet cannot be sagging."""
    s = _state(tmp_path)
    s.chapters[1] = _flat(1, status="planned")
    assert chapter_activity(s, 1).is_flat is False


def test_book_shape_is_in_reading_order(tmp_path):
    s = _state(tmp_path)
    for n in (3, 1, 2):
        s.chapters[n] = _flat(n)
    assert [a.number for a in book_shape(s)] == [1, 2, 3]


# ------------------------------------------------------------------ runs

def test_three_flat_chapters_are_a_stall(tmp_path):
    s = _state(tmp_path)
    for n in (1, 2, 3):
        s.chapters[n] = _flat(n)
    runs = find_stalls(s)
    assert len(runs) == 1
    assert (runs[0].start, runs[0].end, runs[0].length) == (1, 3, 3)


def test_two_flat_chapters_are_a_breather_not_a_stall(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    s.chapters[2] = _flat(2)
    assert find_stalls(s) == []


def test_a_moving_chapter_breaks_the_run(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    s.chapters[2] = _flat(2)
    s.chapters[3] = _moving(3)
    s.chapters[4] = _flat(4)
    s.chapters[5] = _flat(5)
    assert find_stalls(s) == []


def test_an_unwritten_chapter_breaks_the_run(tmp_path):
    """The sag might simply not be drafted yet - do not report across a gap."""
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    s.chapters[2] = _flat(2)
    s.chapters[3] = _flat(3, status="planned")
    s.chapters[4] = _flat(4)
    assert find_stalls(s) == []


def test_a_run_at_the_end_of_the_book_is_still_reported(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _moving(1)
    for n in (2, 3, 4):
        s.chapters[n] = _flat(n)
    assert [(r.start, r.end) for r in find_stalls(s)] == [(2, 4)]


def test_two_separate_stalls_are_reported_separately(tmp_path):
    s = _state(tmp_path)
    for n in (1, 2, 3):
        s.chapters[n] = _flat(n)
    s.chapters[4] = _moving(4)
    for n in (5, 6, 7):
        s.chapters[n] = _flat(n)
    assert [(r.start, r.end) for r in find_stalls(s)] == [(1, 3), (5, 7)]


def test_run_length_is_configurable(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1)
    s.chapters[2] = _flat(2)
    assert len(find_stalls(s, run_length=2)) == 1


# ----------------------------------------------------------- the message

def test_a_single_pov_run_names_the_reactive_protagonist(tmp_path):
    s = _state(tmp_path)
    for n in (1, 2, 3):
        s.chapters[n] = _flat(n, pov="Lena")
    assert "Lena" in find_stalls(s)[0].reason
    assert "reactive" in find_stalls(s)[0].reason


def test_a_mixed_pov_run_describes_the_stretch_instead(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _flat(1, pov="Lena")
    s.chapters[2] = _flat(2, pov="Mara")
    s.chapters[3] = _flat(3, pov="Kesh")
    reason = find_stalls(s)[0].reason
    assert "no plot advance" in reason


# --------------------------------------------------- continuity integration

def test_stalls_surface_as_continuity_findings(tmp_path):
    s = _state(tmp_path)
    for n in (1, 2, 3):
        s.chapters[n] = _flat(n)
    findings = run_all(s)
    stall = next(f for f in findings if f.category == "stalled_middle")
    assert stall.severity == "warning"
    assert "1-3" in stall.message
    assert stall.suggestion


def test_a_stall_finding_can_be_marked_intentional(tmp_path):
    """Slow burns are a deliberate choice; the writer must be able to say so."""
    s = _state(tmp_path)
    for n in (1, 2, 3):
        s.chapters[n] = _flat(n)
    stall = next(f for f in run_all(s) if f.category == "stalled_middle")

    s.exempt_finding(stall.key, "deliberate slow burn")
    assert not any(f.category == "stalled_middle" for f in run_all(s))


def test_as_of_chapter_does_not_report_stalls_from_the_future(tmp_path):
    s = _state(tmp_path)
    s.chapters[1] = _moving(1)
    for n in (5, 6, 7):
        s.chapters[n] = _flat(n)
    assert not any(
        f.category == "stalled_middle" for f in run_all(s, as_of_chapter=3)
    )


def test_a_healthy_book_reports_no_stall(tmp_path):
    s = _state(tmp_path)
    for n in (1, 2, 3, 4, 5):
        s.chapters[n] = _moving(n)
    assert not any(f.category == "stalled_middle" for f in run_all(s))
