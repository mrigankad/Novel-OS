"""Tests for plot thread prompt formatting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from plot_prompts import format_plot_thread_line, format_plot_threads_block  # noqa: E402
from state_manager import PlotThread  # noqa: E402


def test_format_includes_subplots():
    t = PlotThread(
        id="p1",
        name="Family Estate Arc",
        description="Family fight over the estate",
        thread_type="main",
        subplots=["Jordan finds the letter", "Taylor skips the hearing"],
    )
    line = format_plot_thread_line(t)
    assert "Family Estate Arc" in line
    assert "Subplots:" in line
    assert "Jordan finds the letter" in line


def test_format_threads_block():
    threads = [
        PlotThread(id="a", name="A", description="", thread_type="main"),
        PlotThread(id="b", name="B", description="", thread_type="subplot"),
    ]
    block = format_plot_threads_block(threads)
    assert "### Active Plot Threads" in block
    assert "**A**" in block
    assert "**B**" in block
