"""Tests for background job runner."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from jobs import JobRunner


def test_list_running_includes_label_and_meta():
    runner = JobRunner()
    started = threading.Event()

    def work():
        started.wait(timeout=2)

    job_id = runner.submit(
        "mine_plots",
        work,
        meta={"project_id": "demo-project", "chapter": 3},
    )
    time.sleep(0.05)
    running = runner.list_running()
    assert len(running) == 1
    row = running[0]
    assert row["job_id"] == job_id
    assert row["screen"] == "Chapter"
    assert row["project_id"] == "demo-project"
    assert row["chapter"] == 3
    assert "demo-project" in row["label"]
    assert "Ch.3" in row["label"]
    assert "Mine plot threads" in row["label"]
    started.set()
