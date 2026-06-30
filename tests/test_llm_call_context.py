"""Tests for LLM job label context."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from llm_call_context import format_llm_job_label, llm_job_context, resolve_llm_label, screen_for_kind


def test_format_llm_job_label_with_chapter_and_time():
    label = format_llm_job_label(
        "mine_plots",
        {"project_id": "demo-project", "chapter": 4},
        started_at="2026-06-29T19:22:00+00:00",
    )
    assert label == "Chapter · demo-project · Ch.4 · Mine plot threads · 2026-06-29 19:22"


def test_screen_for_dedup_on_plots():
    assert screen_for_kind("dedup_ai", {}) == "Plots"


def test_resolve_llm_label_uses_context():
    with llm_job_context("Plots · p · Resolve duplicates · 2026-06-29 19:22"):
        assert resolve_llm_label() == "Plots · p · Resolve duplicates · 2026-06-29 19:22"
        assert resolve_llm_label("Override") == "Override"
    assert resolve_llm_label().startswith("App · LLM request · ")
