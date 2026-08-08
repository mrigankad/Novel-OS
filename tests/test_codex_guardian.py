"""Codex formatting for Guardian prompts + sample project seed."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import Character, CodexEntry, StoryState  # noqa: E402


def test_format_codex_block_includes_types(tmp_path):
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    state = StoryState(str(root))
    state.set_metadata("title", "T")
    state.add_character(Character(
        id="char_001", full_name="Lena Marrow", role="protagonist",
        notes="Owns a brass compass.",
    ))
    state.add_codex_entry(CodexEntry(
        id="loc-001", entry_type="location", name="Glass Harbor",
        summary="Fogbound port.",
    ))
    state.add_codex_entry(CodexEntry(
        id="wor-001", entry_type="worldbuilding", name="Salt-oil",
        summary="Blue flame normal; red means quarantine.",
    ))
    block = state.format_codex_block()
    assert "Lena Marrow" in block
    assert "Glass Harbor" in block
    assert "Salt-oil" in block
    assert "ground truth" in block.lower()
    ctx = state.get_continuity_context(1)
    # Continuity context uses ranked packs (not the raw dump)
    assert "Lena Marrow" in ctx["codex_block"]
    assert "Glass Harbor" in ctx["codex_block"]
    assert "Context pack" in ctx["codex_block"]


def test_validation_prompt_embeds_codex(tmp_path, monkeypatch):
    from orchestrator import NovelOrchestrator

    root = tmp_path / "harbor"
    orch = NovelOrchestrator(str(root))
    orch.init_project("Harbor", "Literary", "Ada")
    orch.add_character("Lena Marrow", "protagonist")
    s = orch.state
    s.add_codex_entry(CodexEntry(
        id="loc-001", entry_type="location", name="Glass Harbor",
        summary="Fogbound port with blue lanterns.",
    ))
    prompt = orch._generate_validation_prompt(1, "Lena stood on the pier at Glass Harbor.")
    assert "Context pack" in prompt
    assert "Glass Harbor" in prompt
    assert "Lena Marrow" in prompt
    assert "Do not invent Codex facts" in prompt


def _client(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    return TestClient(create_app(
        projects_root=projects,
        db_url=f"sqlite:///{(tmp_path / 't.db').as_posix()}",
        media_root=tmp_path / "media",
    ))


def test_sample_project_seed_idempotent(tmp_path):
    client = _client(tmp_path)
    a = client.post("/api/projects/sample")
    assert a.status_code == 201, a.text
    body = a.json()
    assert "Glass Harbor" in body["title"]
    pid = body["id"]

    codex = client.get(f"/api/projects/{pid}/codex").json()
    types = {e["entry_type"] for e in codex}
    assert "character" in types
    assert "location" in types
    assert "worldbuilding" in types
    assert "item" in types

    chapters = client.get(f"/api/projects/{pid}/chapters").json()
    assert any(c["number"] == 1 for c in chapters)

    b = client.post("/api/projects/sample")
    assert b.status_code == 201
    assert b.json()["id"] == pid
