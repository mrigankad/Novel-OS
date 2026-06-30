"""API test for nest plot threads."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path):
    db_url = f"sqlite:///{(Path(tmp_path) / 'novel_os_test.db').as_posix()}"
    return TestClient(create_app(projects_root=tmp_path, db_url=db_url))


def _seed(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True)
    data = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {},
        "plot_threads": {
            "plot_a": {
                "id": "plot_a", "name": "Main", "description": "Primary arc",
                "thread_type": "main", "status": "active", "priority": 5,
                "sort_order": 0, "subplots": [],
            },
            "plot_b": {
                "id": "plot_b", "name": "B-plot", "description": "Secondary",
                "thread_type": "subplot", "status": "active", "priority": 3,
                "sort_order": 1, "subplots": ["Existing beat"],
            },
        },
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(data), encoding="utf-8")


def test_nest_plot_threads_endpoint(tmp_path):
    _seed(tmp_path)
    c = _client(tmp_path)
    resp = c.post(
        "/api/projects/p/plot-threads/nest",
        json={"parent_id": "plot_a", "child_ids": ["plot_b"]},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "nest"
    rows = c.get("/api/projects/p/plot-threads").json()
    assert len(rows) == 1
    assert any("B-plot" in s for s in rows[0]["subplots"])
