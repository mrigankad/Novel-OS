"""Manuscript statistics / Style Curator surface (PLAN.md P4)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from style_stats import analyze_manuscript, find_echoes, tokenize


def test_analyze_manuscript_counts_and_top_words():
    text = (
        "The harbor lights flickered. Mara watched the harbor from the pier. "
        "Harbor wind cut across the pier again. She waited by the pier."
    )
    stats = analyze_manuscript([text])
    assert stats["word_count"] > 10
    assert stats["reading_minutes"] >= 1
    words = {w["word"]: w["count"] for w in stats["top_words"]}
    assert words.get("harbor", 0) >= 2
    assert words.get("pier", 0) >= 2
    assert "the" not in words


def test_find_echoes_flags_close_repeats():
    tokens = tokenize(
        "glass glass glass window window window door silence silence silence"
    )
    echoes = {e["word"]: e for e in find_echoes(tokens, window=40, min_count=3)}
    assert "glass" in echoes
    assert echoes["glass"]["count"] >= 3


def _seed(root: Path, slug: str, prose: str) -> None:
    state = root / slug / "outputs" / "state"
    state.mkdir(parents=True)
    (state / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Signal", "genre": "SF", "author": "A"},
        "chapters": {
            "1": {
                "number": 1, "title": "One", "status": "drafted",
                "word_count": len(prose.split()), "pov_character": "Mara",
                "target_word_count": 2500, "scenes": [], "notes": "",
            },
        },
        "characters": {}, "plot_threads": {}, "timeline": [],
        "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    chap = root / slug / "outputs" / "manuscript"
    chap.mkdir(parents=True)
    (chap / "chapter_001_draft.md").write_text(prose, encoding="utf-8")


def test_statistics_endpoint(tmp_path):
    root = tmp_path / "projects"
    prose = (
        "Mara climbed the lattice. The lattice shivered under her boots. "
        "Lattice cables hummed as she climbed again toward the signal mast."
    )
    _seed(root, "signal", prose)
    client = TestClient(create_app(
        projects_root=root,
        db_url=f"sqlite:///{(tmp_path / 's.db').as_posix()}",
    ))

    resp = client.get("/api/projects/signal/statistics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapter_count"] == 1
    assert body["chapters_with_prose"] == 1
    assert body["word_count"] > 0
    assert body["reading_minutes"] >= 1
    top = {w["word"]: w["count"] for w in body["top_words"]}
    assert top.get("lattice", 0) >= 2
    assert any(e["word"] == "lattice" for e in body["echoes"])


def test_statistics_404(tmp_path):
    client = TestClient(create_app(
        projects_root=tmp_path / "projects",
        db_url=f"sqlite:///{(tmp_path / 'x.db').as_posix()}",
    ))
    assert client.get("/api/projects/missing/statistics").status_code == 404
