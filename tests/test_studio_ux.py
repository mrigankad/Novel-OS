"""Tests for Studio LLM settings + richer project summaries."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api.main import create_app


def _client(tmp_path, monkeypatch):
    settings = tmp_path / "studio_settings.json"
    monkeypatch.setenv("NOVEL_OS_SETTINGS_PATH", str(settings))
    projects = tmp_path / "projects"
    projects.mkdir()
    app = create_app(projects_root=projects, db_url=f"sqlite:///{tmp_path / 't.db'}")
    return TestClient(app), settings


def test_llm_status_endpoint(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.get("/api/studio/llm").json()
    assert "configured" in body
    assert "presets" in body
    assert {p["id"] for p in body["presets"]} >= {"quality", "fast", "local", "mature"}


def test_llm_put_preset_persists(tmp_path, monkeypatch):
    client, settings = _client(tmp_path, monkeypatch)
    resp = client.put("/api/studio/llm", json={"preset": "local", "onboarding_completed": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["preset"] == "local"
    assert body["onboarding_completed"] is True
    saved = json.loads(settings.read_text(encoding="utf-8"))
    assert saved["preset"] == "local"
    assert saved["NOVEL_OS_LLM_PROVIDER"] == "ollama"
    assert saved["onboarding_completed"] is True


def test_project_summary_includes_words_and_rating(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    created = client.post("/api/projects", json={
        "title": "The Last Signal", "genre": "Romance", "author": "Ada",
    }).json()
    assert created["author"] == "Ada"
    assert created["content_rating"] == "general"
    assert "word_count" in created

    items = client.get("/api/projects").json()
    assert len(items) == 1
    assert items[0]["title"] == "The Last Signal"

    detail = client.patch(f"/api/projects/{created['id']}", json={"content_rating": "mature"}).json()
    assert detail["content_rating"] == "mature"

    again = client.get("/api/projects").json()[0]
    assert again["content_rating"] == "mature"
