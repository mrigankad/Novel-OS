"""Outliner tension / emotion / pacing metrics (PLAN.md P4)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from chapter_metrics import score_chapter


def test_score_chapter_raises_on_tense_prose():
    calm = score_chapter(
        "She walked to the market and bought bread. The sun was warm."
    )
    tense = score_chapter(
        "Blood hit the knife. She fled the trap. Fear. Escape. The enemy hunted her. "
        "Scream! Chase! Danger closed in. Attack. Kill or die."
    )
    assert 1 <= calm["tension"] <= 10
    assert tense["tension"] > calm["tension"]
    assert tense["pacing"] >= calm["pacing"]


def test_score_chapter_emotion_lexicon():
    flat = score_chapter("The door opened. A chair sat by the wall.")
    felt = score_chapter(
        "Grief flooded her heart. Tears of longing and despair. Love ached. "
        "She wept with sorrow and lonely shame."
    )
    assert felt["emotional_intensity"] > flat["emotional_intensity"]


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
            "2": {
                "number": 2, "title": "Two", "status": "planned",
                "word_count": 0, "pov_character": "Mara",
                "target_word_count": 2500, "scenes": [], "notes": "",
            },
        },
        "characters": {}, "plot_threads": {}, "timeline": [],
        "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    ms = root / slug / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    (ms / "chapter_001_draft.md").write_text(prose, encoding="utf-8")


def test_outliner_metrics_refresh_persists_derived(tmp_path):
    root = tmp_path / "projects"
    prose = (
        "Mara fled the trap. Fear clawed her throat. The enemy hunted through blood "
        "and smoke. Escape! Knife flash. Danger closed. She screamed and ran."
    )
    _seed(root, "signal", prose)
    client = TestClient(create_app(
        projects_root=root,
        db_url=f"sqlite:///{(tmp_path / 'm.db').as_posix()}",
    ))

    resp = client.post("/api/projects/signal/outliner/metrics/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "heuristic"
    assert len(body["chapters"]) == 2
    ch1 = next(c for c in body["chapters"] if c["chapter"] == 1)
    assert 1 <= ch1["tension"] <= 10
    assert 1 <= ch1["emotional_intensity"] <= 10
    assert 1 <= ch1["pacing"] <= 10

    tree = client.get("/api/projects/signal/binder").json()
    chapter_nodes = tree[0]["children"]
    one = next(n for n in chapter_nodes if n["chapter_number"] == 1)
    assert one["derived"]["tension"] == ch1["tension"]
    assert one["derived"]["pacing"] == ch1["pacing"]


def test_outliner_metrics_single_chapter(tmp_path):
    root = tmp_path / "projects"
    _seed(root, "signal", "She waited by the quiet window.")
    client = TestClient(create_app(
        projects_root=root,
        db_url=f"sqlite:///{(tmp_path / 'm2.db').as_posix()}",
    ))
    resp = client.post("/api/projects/signal/outliner/metrics/refresh?chapter=1")
    assert resp.status_code == 200
    assert [c["chapter"] for c in resp.json()["chapters"]] == [1]
