"""Architect corkboard synopsis refresh (PLAN.md P4.3)."""

import json

from fastapi.testclient import TestClient

from api.main import create_app
from state_manager import ChapterState


def _client(tmp_path):
    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "manuscript").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A", "premise": "Signals in the fog."},
        "chapters": {"1": ChapterState(number=1, title="One", pov_character="Lena").to_dict()},
    }), encoding="utf-8")
    (proj / "outputs" / "chapter_001_outline.md").write_text(
        "# Chapter 1: One\n\n## Chapter Goal\n"
        "Lena finds the red lantern and the compass refuses north.\n\n"
        "## Beats\n- pier\n- lantern\n",
        encoding="utf-8",
    )
    app = create_app(
        projects_root=root,
        db_url=f"sqlite:///{tmp_path / 's.db'}",
    )
    return TestClient(app)


def test_refresh_synopsis_falls_back_to_outline_goal(tmp_path, monkeypatch):
    """Without a working LLM, heuristic uses the Chapter Goal section."""
    import api.services as services

    class Boom:
        def _get_llm(self):
            raise RuntimeError("no llm")

    monkeypatch.setattr(services, "build_orchestrator", lambda *_a, **_k: Boom())

    client = _client(tmp_path)
    resp = client.post("/api/projects/book/chapters/1/synopsis/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "heuristic"
    assert "red lantern" in body["synopsis"].lower() or "compass" in body["synopsis"].lower()

    tree = client.get("/api/projects/book/binder").json()
    assert "lantern" in tree[0]["children"][0]["synopsis"].lower() or \
           "compass" in tree[0]["children"][0]["synopsis"].lower()


def test_refresh_synopsis_uses_architect_when_llm_works(tmp_path, monkeypatch):
    import api.services as services

    class FakeLlm:
        def run_agent(self, _agent, _prompt):
            return "Lena tracks a rogue signal to the red quay lantern."

    class FakeOrch:
        def _get_llm(self):
            return FakeLlm()

    monkeypatch.setattr(services, "build_orchestrator", lambda *_a, **_k: FakeOrch())
    monkeypatch.setattr(services, "_current_model_label", lambda: "claude:test")

    client = _client(tmp_path)
    resp = client.post("/api/projects/book/chapters/1/synopsis/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "architect"
    assert "rogue signal" in body["synopsis"].lower()
    assert body["model"] == "claude:test"
