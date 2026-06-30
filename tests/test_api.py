import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import ProjectService


def _seed_project(root: Path, slug: str, title: str, genre: str,
                  chapters: dict | None = None) -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": title, "genre": genre, "author": "Test Author"},
        "characters": {},
        "plot_threads": {},
        "chapters": chapters or {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")


@pytest.fixture
def projects_root(tmp_path):
    _seed_project(tmp_path, "the-last-signal", "The Last Signal", "Sci-Fi Thriller")
    return tmp_path


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_prompt_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    c = TestClient(create_app())
    assert c.get("/api/settings/system-prompt").json()["prefix"] == ""
    c.put("/api/settings/system-prompt", json={"prefix": "Be concise.", "agents_dir": ""})
    assert c.get("/api/settings/system-prompt").json()["prefix"] == "Be concise."


def test_llm_queue_settings_and_flush(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    import llm_queue as lq

    lq._queue = None
    c = TestClient(create_app())

    default = c.get("/api/settings/llm-queue")
    assert default.status_code == 200
    assert default.json()["max_concurrent"] == 2
    assert default.json()["active"] == 0

    updated = c.put("/api/settings/llm-queue", json={"max_concurrent": 3})
    assert updated.status_code == 200
    assert updated.json()["max_concurrent"] == 3

    flushed = c.post("/api/settings/llm-queue/flush")
    assert flushed.status_code == 200
    assert flushed.json()["queue"]["flushed"] is True
    lq._queue = None


def test_list_projects(projects_root):
    svc = ProjectService(projects_root)
    projects = svc.list_projects()
    assert len(projects) == 1
    assert projects[0].id == "the-last-signal"
    assert projects[0].title == "The Last Signal"
    assert projects[0].chapter_count == 0


def _client(projects_root):
    db_url = f"sqlite:///{(Path(projects_root) / 'novel_os_test.db').as_posix()}"
    app = create_app(projects_root=projects_root, db_url=db_url)
    return TestClient(app)


def test_get_projects_endpoint(projects_root):
    resp = _client(projects_root).get("/api/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == "the-last-signal"


def test_project_detail(projects_root):
    resp = _client(projects_root).get("/api/projects/the-last-signal")
    assert resp.status_code == 200
    assert resp.json()["author"] == "Test Author"


def test_project_detail_404(projects_root):
    resp = _client(projects_root).get("/api/projects/nope")
    assert resp.status_code == 404


def test_chapters_list(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 2300, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    resp = _client(tmp_path).get("/api/projects/p/chapters")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["number"] == 1
    assert rows[0]["title"] == "Opening"
    assert rows[0]["pipeline_step"] == "drafted"


def test_chapter_pipeline_step_from_files(tmp_path):
    chapters = {"1": {"number": 1, "title": "Ch1", "status": "complete",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    ms = proj / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    (ms / "chapter_001_final.md").write_text("Final prose here.", encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "final"


def test_chapter_pipeline_step_validated(tmp_path):
    chapters = {"1": {"number": 1, "title": "Ch1", "status": "validated",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    ms = tmp_path / "p" / "outputs" / "manuscript"
    ms.mkdir(parents=True)
    (ms / "chapter_001_revised.md").write_text("Revised.", encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "validated"


def test_update_chapter_title(tmp_path):
    chapters = {"1": {"number": 1, "title": "", "status": "drafted",
                      "word_count": 100, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    c = _client(tmp_path)
    resp = c.patch("/api/projects/p/chapters/1", json={"title": "The Archive"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "The Archive"
    detail = c.get("/api/projects/p/chapters/1").json()
    assert detail["title"] == "The Archive"
    list_row = c.get("/api/projects/p/chapters").json()[0]
    assert list_row["title"] == "The Archive"


def test_chapter_detail_with_files(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 5, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "chapter_001_outline.md").write_text("# Beat sheet", encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("Prose here", encoding="utf-8")
    resp = _client(tmp_path).get("/api/projects/p/chapters/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["outline"] == "# Beat sheet"
    assert body["draft"] == "Prose here"


def test_chapter_detail_missing_files(tmp_path):
    chapters = {"2": {"number": 2, "title": "", "status": "planned",
                      "word_count": 0, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    body = _client(tmp_path).get("/api/projects/p/chapters/2").json()
    assert body["outline"] is None
    assert body["draft"] is None


def test_chapter_404(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    resp = _client(tmp_path).get("/api/projects/p/chapters/9")
    assert resp.status_code == 404


def test_characters_endpoint(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {"char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"}}
    sf.write_text(json.dumps(data), encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/characters").json()
    assert rows[0]["full_name"] == "Lena"


# --- M2: chapter stages + editable Final -------------------------------------

def _seed_chapter_files(root: Path, slug: str, number: int,
                        outline=None, draft=None, revised=None, final=None) -> None:
    proj = root / slug / "outputs"
    nnn = f"{number:03d}"
    (proj / "manuscript").mkdir(parents=True, exist_ok=True)
    if outline is not None:
        (proj / f"chapter_{nnn}_outline.md").write_text(outline, encoding="utf-8")
    if draft is not None:
        (proj / "manuscript" / f"chapter_{nnn}_draft.md").write_text(draft, encoding="utf-8")
    if revised is not None:
        (proj / "manuscript" / f"chapter_{nnn}_revised.md").write_text(revised, encoding="utf-8")
    if final is not None:
        (proj / "manuscript" / f"chapter_{nnn}_final.md").write_text(final, encoding="utf-8")


def _seed_with_chapter(tmp_path, number=1, status="drafted", **files):
    chapters = {str(number): {"number": number, "title": "Opening", "status": status,
                              "word_count": 0, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", number, **files)


def test_stages_returns_all_present_artifacts(tmp_path):
    _seed_with_chapter(tmp_path, outline="# Beats", draft="Draft text", revised="Revised text")
    body = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert body["outline"] == "# Beats"
    assert body["draft"] == "Draft text"
    assert body["revised"] == "Revised text"
    assert body["final"] is None


def test_stages_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).get("/api/projects/p/chapters/9/stages").status_code == 404


def test_promote_final_prefers_revised(tmp_path):
    _seed_with_chapter(tmp_path, draft="Draft text", revised="Revised text")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.status_code == 200
    assert resp.json()["final"] == "Revised text"
    # now present in stages
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["final"] == "Revised text"


def test_promote_final_falls_back_to_draft(tmp_path):
    _seed_with_chapter(tmp_path, draft="Only draft")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.json()["final"] == "Only draft"


def test_promote_final_conflict_when_no_source(tmp_path):
    _seed_with_chapter(tmp_path)  # no artifacts at all
    assert _client(tmp_path).post("/api/projects/p/chapters/1/final/promote").status_code == 409


def test_promote_is_idempotent_without_force(tmp_path):
    _seed_with_chapter(tmp_path, revised="Revised", final="Hand-edited final")
    # already has a final — promote without force must not clobber the human edit
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/promote")
    assert resp.json()["final"] == "Hand-edited final"


def test_save_final_writes_and_updates_word_count(tmp_path):
    _seed_with_chapter(tmp_path, draft="x")
    resp = _client(tmp_path).put("/api/projects/p/chapters/1/final", json={"text": "one two three"})
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 3
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["final"] == "one two three"


def test_save_revised_writes_and_updates_status(tmp_path):
    _seed_with_chapter(tmp_path, draft="draft", revised="old revised")
    resp = _client(tmp_path).put("/api/projects/p/chapters/1/revised", json={"text": "new revised text"})
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 3
    assert _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()["revised"] == "new revised text"


def test_save_final_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).put("/api/projects/p/chapters/9/final",
                                 json={"text": "x"}).status_code == 404


def test_unfinalize_copies_final_to_draft_and_revised(tmp_path):
    _seed_with_chapter(
        tmp_path, status="complete",
        draft="Old draft", revised="Old revised", final="Canonical final prose here",
    )
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["final"] is None
    assert body["draft"] == "Canonical final prose here"
    assert body["revised"] == "Canonical final prose here"
    assert body["status"] == "edited"
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["final"] is None
    assert stages["draft"] == "Canonical final prose here"
    assert stages["continuity"] is None
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_reopens_complete_without_final(tmp_path):
    _seed_with_chapter(tmp_path, status="complete", draft="Draft", revised="Revised")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    assert resp.json()["status"] == "edited"
    assert resp.json()["draft"] == "Draft"
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_clears_validated_and_final(tmp_path):
    chapters = {
        "1": {
            "number": 1, "title": "Ch", "status": "validated",
            "word_count": 10, "pov_character": "",
            "continuity_checks": {"status": "PASS", "validated_at": "2026-01-01"},
        },
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, revised="Revised text", final="Final canon")
    resp = _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "edited"
    assert body["final"] is None
    assert body["revised"] == "Final canon"
    stages = _client(tmp_path).get("/api/projects/p/chapters/1/stages").json()
    assert stages["continuity"] is None
    rows = _client(tmp_path).get("/api/projects/p/chapters").json()
    assert rows[0]["pipeline_step"] == "revised"


def test_unfinalize_conflict_when_nothing_to_reopen(tmp_path):
    _seed_with_chapter(tmp_path, status="drafted", draft="Only draft")
    assert _client(tmp_path).post("/api/projects/p/chapters/1/final/unfinalize").status_code == 409


# --- Tier 0: create / run / export -------------------------------------------

import time

import api.services as services


def test_create_project_then_lists(tmp_path):
    c = _client(tmp_path)
    resp = c.post("/api/projects", json={"title": "The Drowned City", "genre": "Fantasy"})
    assert resp.status_code == 201
    assert resp.json()["id"] == "the-drowned-city"
    ids = [p["id"] for p in c.get("/api/projects").json()]
    assert "the-drowned-city" in ids


def test_create_project_requires_title(tmp_path):
    assert _client(tmp_path).post("/api/projects", json={"title": "  "}).status_code == 400


def test_add_character(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    resp = _client(tmp_path).post("/api/projects/p/characters",
                                  json={"name": "Mara Vale", "role": "protagonist"})
    assert resp.status_code == 201
    assert any(c["full_name"] == "Mara Vale" for c in resp.json())


def _wait_job(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.03)
    return client.get(f"/api/jobs/{job_id}").json()


class _FakeOrch:
    calls: list = []

    def __init__(self, _dir):
        pass

    def write_chapter(self, n):
        _FakeOrch.calls.append(("write", n))


def test_run_phase_job_lifecycle(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama")
    _FakeOrch.calls = []
    monkeypatch.setattr(services, "build_orchestrator", lambda d: _FakeOrch(d))
    c = _client(tmp_path)
    resp = c.post("/api/projects/p/run", json={"stage": "write", "params": {"number": 1}})
    assert resp.status_code == 202
    job = _wait_job(c, resp.json()["job_id"])
    assert job["status"] == "done"
    assert _FakeOrch.calls == [("write", 1)]


def test_run_unknown_stage_400(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).post("/api/projects/p/run",
                                  json={"stage": "nope", "params": {}}).status_code == 400


def test_run_job_captures_error(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama")

    def boom(_dir):
        class O:
            def write_chapter(self, n):
                raise RuntimeError("LLM exploded")
        return O()

    monkeypatch.setattr(services, "build_orchestrator", boom)
    c = _client(tmp_path)
    job_id = c.post("/api/projects/p/run", json={"stage": "write", "params": {"number": 1}}).json()["job_id"]
    job = _wait_job(c, job_id)
    assert job["status"] == "error"
    assert "LLM exploded" in job["error"]


def test_export_prefers_final(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "complete",
                      "word_count": 2, "pov_character": ""}}
    _seed_project(tmp_path, "p", "Compiled Tale", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, draft="DRAFT body", final="FINAL body")
    text = _client(tmp_path).get("/api/projects/p/export").text
    assert "Compiled Tale" in text
    assert "FINAL body" in text
    assert "DRAFT body" not in text


def test_export_import_project_package(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "drafted",
                      "word_count": 3, "pov_character": ""}}
    _seed_project(tmp_path, "source", "Shared Novel", "Sci-Fi", chapters=chapters)
    _seed_chapter_files(tmp_path, "source", 1, draft="chapter one")
    c = _client(tmp_path)
    dbmod.ingest_project(tmp_path, "source")

    export = c.get("/api/projects/source/export-package")
    assert export.status_code == 200
    assert export.headers["content-type"] == "application/zip"
    assert export.content[:2] == b"PK"

    imported = c.post(
        "/api/projects/import-package",
        content=export.content,
        headers={"Content-Type": "application/zip"},
    )
    assert imported.status_code == 201
    body = imported.json()
    assert body["id"] == "shared-novel"
    assert body["title"] == "Shared Novel"
    assert body["chapter_count"] == 1
    assert (tmp_path / "shared-novel" / "outputs" / "state" / "story_state.json").exists()
    assert c.get("/api/projects/shared-novel").status_code == 200


def test_import_package_rejects_invalid_zip(tmp_path):
    c = _client(tmp_path)
    resp = c.post(
        "/api/projects/import-package",
        content=b"not a zip",
        headers={"Content-Type": "application/zip"},
    )
    assert resp.status_code == 400


# --- Tier 1: snapshots + comments + DB ingest ---------------------------------

import api.db as dbmod


def test_snapshot_lifecycle(tmp_path):
    _seed_with_chapter(tmp_path, draft="draft body")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    r = c.post("/api/projects/p/chapters/1/snapshots", json={"label": "v1"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert any(s["id"] == sid for s in c.get("/api/projects/p/chapters/1/snapshots").json())
    got = c.get(f"/api/projects/p/chapters/1/snapshots/{sid}").json()
    assert got["text"] == "draft body" and got["label"] == "v1"


def test_snapshot_409_without_final(tmp_path):
    _seed_with_chapter(tmp_path)
    assert _client(tmp_path).post("/api/projects/p/chapters/1/snapshots", json={}).status_code == 409


def test_snapshot_restore_makes_backup(tmp_path):
    _seed_with_chapter(tmp_path, draft="orig")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    sid = c.post("/api/projects/p/chapters/1/snapshots", json={"label": "v1"}).json()["id"]
    c.put("/api/projects/p/chapters/1/final", json={"text": "changed"})
    r = c.post(f"/api/projects/p/chapters/1/snapshots/{sid}/restore")
    assert r.status_code == 200 and r.json()["final"] == "orig"
    assert c.get("/api/projects/p/chapters/1/stages").json()["final"] == "orig"
    labels = [s["label"] for s in c.get("/api/projects/p/chapters/1/snapshots").json()]
    assert "Before restore" in labels


def test_snapshot_delete(tmp_path):
    _seed_with_chapter(tmp_path, draft="x")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")
    sid = c.post("/api/projects/p/chapters/1/snapshots", json={}).json()["id"]
    assert c.delete(f"/api/projects/p/chapters/1/snapshots/{sid}").status_code == 204
    assert c.get("/api/projects/p/chapters/1/snapshots").json() == []


def test_comment_crud(tmp_path):
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/comments", json={"body": "tighten this", "quote": "the pipe"})
    assert r.status_code == 201
    cid = r.json()["id"]
    rows = c.get("/api/projects/p/chapters/1/comments").json()
    assert rows[0]["body"] == "tighten this" and rows[0]["quote"] == "the pipe"
    up = c.patch(f"/api/projects/p/chapters/1/comments/{cid}", json={"resolved": True})
    assert up.json()["resolved"] is True
    assert c.delete(f"/api/projects/p/chapters/1/comments/{cid}").status_code == 204
    assert c.get("/api/projects/p/chapters/1/comments").json() == []


def test_comment_requires_body(tmp_path):
    _seed_with_chapter(tmp_path)
    assert _client(tmp_path).post("/api/projects/p/chapters/1/comments", json={"body": "  "}).status_code == 400


def test_ingest_mirrors_content_to_db(tmp_path):
    _seed_with_chapter(tmp_path, outline="# Beats", draft="draft body")
    c = _client(tmp_path)
    c.post("/api/projects/p/chapters/1/final/promote")  # dual-writes final to DB
    assert dbmod.get_artifact_text("p", 1, "final") == "draft body"
    c.get("/api/projects/p/chapters/1/stages")  # triggers ingest of outline/draft
    assert dbmod.get_artifact_text("p", 1, "outline") == "# Beats"
    assert dbmod.get_artifact_text("p", 1, "draft") == "draft body"


# --- Delete operations --------------------------------------------------------

def test_delete_character(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {"char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"}}
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p/characters/char_001").status_code == 204
    assert c.get("/api/projects/p/characters").json() == []


def test_character_aliases_round_trip(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_jordan": {
            "id": "char_jordan", "full_name": "Jordan Lee", "role": "protagonist",
            "aliases": ["Nickname"],
        }
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    listed = c.get("/api/projects/p/characters").json()
    assert listed[0]["aliases"] == ["Nickname"]
    detail = c.get("/api/projects/p/characters/char_jordan").json()
    assert detail["aliases"] == ["Nickname"]
    patched = c.patch(
        "/api/projects/p/characters/char_jordan",
        json={"aliases": ["Nickname", "Ms. Lee", "Mrs Quinn"]},
    )
    assert patched.status_code == 200
    assert patched.json()["aliases"] == ["Nickname", "Ms. Lee", "Mrs Quinn"]


def test_delete_plot_thread(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_main": {
            "id": "plot_main", "name": "The Quest", "description": "Find it",
            "thread_type": "main", "status": "active", "priority": 5,
            "sort_order": 0, "subplots": ["Side quest"],
        },
        "plot_b": {
            "id": "plot_b", "name": "Romance", "description": "",
            "thread_type": "subplot", "status": "active", "priority": 3,
            "sort_order": 1, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    rows = c.get("/api/projects/p/plot-threads").json()
    assert rows[0]["name"] == "The Quest"
    assert rows[0]["subplots"] == ["Side quest"]
    assert c.delete("/api/projects/p/plot-threads/plot_main").status_code == 204
    assert len(c.get("/api/projects/p/plot-threads").json()) == 1


def test_reorder_plot_threads(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_a": {
            "id": "plot_a", "name": "First", "description": "", "thread_type": "main",
            "status": "active", "priority": 5, "sort_order": 0, "subplots": [],
        },
        "plot_b": {
            "id": "plot_b", "name": "Second", "description": "", "thread_type": "main",
            "status": "active", "priority": 3, "sort_order": 1, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    resp = c.put(
        "/api/projects/p/plot-threads/reorder",
        json={"ordered_ids": ["plot_b", "plot_a"]},
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert names == ["Second", "First"]
    assert names == [r["name"] for r in c.get("/api/projects/p/plot-threads").json()]


def test_update_plot_thread_subplots(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_x": {
            "id": "plot_x", "name": "Arc", "description": "Main arc", "thread_type": "main",
            "status": "active", "priority": 4, "sort_order": 0, "subplots": [],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    resp = c.patch(
        "/api/projects/p/plot-threads/plot_x",
        json={"subplots": ["Beat one", "Beat two"]},
    )
    assert resp.status_code == 200
    assert resp.json()["subplots"] == ["Beat one", "Beat two"]


def test_delete_chapter(tmp_path):
    chapters = {"1": {"number": 1, "title": "One", "status": "drafted",
                      "word_count": 5, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    _seed_chapter_files(tmp_path, "p", 1, draft="hello world")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p/chapters/1").status_code == 204
    assert c.get("/api/projects/p/chapters").json() == []
    proj = tmp_path / "p"
    assert not (proj / "outputs" / "manuscript" / "chapter_001_draft.md").exists()


def test_delete_project(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)
    assert c.delete("/api/projects/p").status_code == 204
    assert c.get("/api/projects").json() == []
    assert not (tmp_path / "p").exists()


def test_reassign_chapter_move(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 5, "pov_character": ""},
        "3": {"number": 3, "title": "Three", "status": "drafted", "word_count": 3, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("chapter one", encoding="utf-8")
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/reassign", json={"to_number": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "moved"
    assert body["to_number"] == 2
    rows = c.get("/api/projects/p/chapters").json()
    nums = sorted(ch["number"] for ch in rows)
    assert nums == [2, 3]
    assert (proj / "outputs" / "manuscript" / "chapter_002_draft.md").exists()
    assert not (proj / "outputs" / "manuscript" / "chapter_001_draft.md").exists()


def test_reassign_chapter_swap(tmp_path):
    chapters = {
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 1, "pov_character": ""},
        "2": {"number": 2, "title": "Two", "status": "drafted", "word_count": 2, "pov_character": ""},
    }
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/reassign", json={"to_number": 2})
    assert r.status_code == 200
    assert r.json()["action"] == "swapped"
    rows = {ch["number"]: ch["title"] for ch in c.get("/api/projects/p/chapters").json()}
    assert rows[1] == "Two"
    assert rows[2] == "One"


def test_extract_background_no_llm(tmp_path, monkeypatch):
    """Endpoint accepts job; we mock extractor to avoid LLM."""
    _seed_project(tmp_path, "p", "P", "Drama")
    from background_extractor import BackgroundExtractor

    def fake_extract(self, text, *, label="Background", dry_run=False, on_progress=None):
        parsed = {
            "block_summary": "Test block",
            "logline": "A test logline",
            "new_characters": ["Jane Doe | protagonist | A hero"],
            "story_bible_notes": ["The world is round"],
        }
        from state_parser import apply_background_to_state
        changes = apply_background_to_state(self.state, parsed, source="lorekeeper", label=label)
        self.state.save_state()
        return changes, "/tmp/report.md"

    monkeypatch.setattr(BackgroundExtractor, "extract", fake_extract)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/extract-background", json={
        "text": "Jane Doe is the hero of this world.",
        "label": "Character bios",
    })
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"
    bible = c.get("/api/projects/p/story-bible").json()["data"]
    assert bible.get("logline") == "A test logline"
    chars = c.get("/api/projects/p/characters").json()
    assert any(ch["full_name"] == "Jane Doe" for ch in chars)


def test_regenerate_preview_apply_discard(tmp_path, monkeypatch):
    _seed_project(tmp_path, "p", "P", "Drama", chapters={
        "1": {"number": 1, "title": "One", "status": "drafted", "word_count": 3, "pov_character": ""},
    })
    proj = tmp_path / "p"
    draft = proj / "outputs" / "manuscript" / "chapter_001_draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("Original chapter prose here.", encoding="utf-8")

    from chapter_regenerator import ChapterRegenerator

    def fake_regenerate(self, number, *, source="draft", instructions="", dry_run=False, on_progress=None):
        preview = "Regenerated chapter prose with more polish."
        self.preview_path(number).write_text(preview, encoding="utf-8")
        self.meta_path(number).parent.mkdir(parents=True, exist_ok=True)
        self.meta_path(number).write_text(
            '{"source":"draft","original_word_count":4,"preview_word_count":6,"generated_at":"now"}',
            encoding="utf-8",
        )
        return preview, "/tmp/report.md"

    monkeypatch.setattr(ChapterRegenerator, "regenerate", fake_regenerate)
    c = _client(tmp_path)

    r = c.post("/api/projects/p/chapters/1/regenerate", json={"source": "draft"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"

    prev = c.get("/api/projects/p/chapters/1/regenerate/preview")
    assert prev.status_code == 200
    assert "Regenerated" in prev.json()["text"]

    applied = c.post("/api/projects/p/chapters/1/regenerate/apply", json={
        "text": prev.json()["text"],
    })
    assert applied.status_code == 200
    assert applied.json()["target"] == "draft"
    assert draft.read_text(encoding="utf-8") == prev.json()["text"]
    assert c.get("/api/projects/p/chapters/1/regenerate/preview").status_code == 404

    # discard path
    r2 = c.post("/api/projects/p/chapters/1/regenerate", json={"source": "draft"})
    job_id2 = r2.json()["job_id"]
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id2}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert c.delete("/api/projects/p/chapters/1/regenerate/preview").status_code == 204
    assert c.get("/api/projects/p/chapters/1/regenerate/preview").status_code == 404


def test_manual_merge_unrelated_names(tmp_path):
    """Manual merge API works when heuristic scan finds no group (different surnames)."""
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_sam_rivera": {
                "id": "char_sam_rivera", "full_name": "Sam Rivera", "role": "minor",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
            "char_sam_ortiz": {
                "id": "char_sam_ortiz", "full_name": "Sam Ortiz (deceased)", "role": "minor",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
        },
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)
    assert c.get("/api/projects/p/duplicates").json()["characters"] == []

    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "character",
        "keep_id": "char_sam_rivera",
        "merge_ids": ["char_sam_ortiz"],
    })
    assert r.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1
    detail = c.get("/api/projects/p/characters/char_sam_rivera").json()
    assert detail["full_name"] == "Sam Ortiz (deceased)"
    assert "Sam Rivera" in detail["aliases"]


def test_duplicates_scan_and_merge(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_nora_blake": {
                "id": "char_nora_blake", "full_name": "Nora Blake", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [],
            },
            "char_nora": {
                "id": "char_nora", "full_name": "Nora", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [],
            },
        },
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    c = _client(tmp_path)

    dup = c.get("/api/projects/p/duplicates")
    assert dup.status_code == 200
    body = dup.json()
    assert len(body["characters"]) >= 1

    group = body["characters"][0]
    keep = group["suggested_keep_id"]
    merge_ids = [m["id"] for m in group["members"] if m["id"] != keep]
    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "character",
        "keep_id": keep,
        "merge_ids": merge_ids,
    })
    assert r.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1

    auto = c.post("/api/projects/p/duplicates/auto-resolve")
    assert auto.status_code == 200


def test_merge_with_label_override_and_ai_prune(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {
            "char_a": {
                "id": "char_a", "full_name": "Nora Blake", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
            "char_b": {
                "id": "char_b", "full_name": "Maya", "role": "supporting",
                "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
            },
        },
        "plot_threads": {
            "plot_a": {
                "id": "plot_a", "name": "Main Quest", "description": "", "thread_type": "main",
                "status": "active", "priority": 5, "sort_order": 0, "subplots": [],
            },
            "plot_b": {
                "id": "plot_b", "name": "The Quest", "description": "", "thread_type": "main",
                "status": "active", "priority": 3, "sort_order": 1, "subplots": [],
            },
        },
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {},
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True, exist_ok=True)
    suggestions = {
        "characters": [{
            "kind": "character",
            "confidence": 0.9,
            "reason": "AI",
            "suggested_keep_id": "char_a",
            "members": [
                {"id": "char_a", "label": "Nora Blake", "role": "supporting"},
                {"id": "char_b", "label": "Maya", "role": "supporting"},
            ],
        }],
        "plot_threads": [{
            "kind": "plot_thread",
            "confidence": 0.88,
            "reason": "AI",
            "suggested_keep_id": "plot_a",
            "members": [
                {"id": "plot_a", "label": "Main Quest", "thread_type": "main"},
                {"id": "plot_b", "label": "The Quest", "thread_type": "main"},
            ],
        }],
    }
    (dedup_dir / "suggestions.json").write_text(json.dumps(suggestions), encoding="utf-8")
    c = _client(tmp_path)

    r = c.post("/api/projects/p/duplicates/merge", json={
        "kind": "plot_thread",
        "keep_id": "plot_a",
        "merge_ids": ["plot_b"],
        "label_override": "The Main Quest Arc",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["keep_label"] == "The Main Quest Arc"

    ai = c.get("/api/projects/p/duplicates?ai=true")
    assert ai.status_code == 200
    assert ai.json()["plot_threads"] == []
    assert len(ai.json()["characters"]) == 1

    plots = c.get("/api/projects/p/plot-threads").json()
    assert len(plots) == 1
    assert plots[0]["name"] == "The Main Quest Arc"


def test_bible_merge_prunes_ai_suggestions(tmp_path):
    state_dir = tmp_path / "p" / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": "P", "genre": "Drama"},
        "characters": {},
        "plot_threads": {},
        "chapters": {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
        "story_bible": {
            "setting_summary": [
                "Harbor Tower is a four-story brick-facade building with an elevator.",
                "Building has four floors above lobby, accessed by elevator.",
            ],
        },
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True, exist_ok=True)
    ai_group = {
        "section": "setting_summary",
        "confidence": 0.95,
        "reason": "Same building description",
        "suggested_keep_index": 0,
        "members": [
            {
                "id": "setting_summary:0",
                "section": "setting_summary",
                "index": 0,
                "label": state["story_bible"]["setting_summary"][0],
            },
            {
                "id": "setting_summary:1",
                "section": "setting_summary",
                "index": 1,
                "label": state["story_bible"]["setting_summary"][1],
            },
        ],
    }
    (dedup_dir / "bible_suggestions.json").write_text(
        json.dumps({"groups": [ai_group]}), encoding="utf-8",
    )
    c = _client(tmp_path)

    before = c.get("/api/projects/p/story-bible/duplicates?ai=true")
    assert before.status_code == 200
    assert len(before.json()["groups"]) == 1

    merged = c.post("/api/projects/p/story-bible/duplicates/merge", json={
        "keep_section": "setting_summary",
        "keep_index": 0,
        "members": ai_group["members"],
        "text_override": "Harbor Tower: four stories, elevator, mirrored lobby.",
    })
    assert merged.status_code == 200
    assert merged.json()["removed"] >= 1
    assert "Harbor Tower" in merged.json()["keep_text"]

    after = c.get("/api/projects/p/story-bible/duplicates?ai=true")
    assert after.status_code == 200
    assert after.json()["groups"] == []

    bible = c.get("/api/projects/p/story-bible").json()["data"]["setting_summary"]
    assert len(bible) == 1
    assert "mirrored lobby" in bible[0]


def test_dedup_status_endpoints(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    c = _client(tmp_path)

    empty_bible = c.get("/api/projects/p/story-bible/duplicates/status")
    assert empty_bible.status_code == 200
    assert empty_bible.json() == {"ai_suggestions_ready": False, "ai_group_count": 0}

    empty_entity = c.get("/api/projects/p/duplicates/status")
    assert empty_entity.status_code == 200
    body = empty_entity.json()
    assert body["ai_suggestions_ready"] is False
    assert body["ai_group_count"] == 0
    assert body["has_ai_file"] is False
    assert body["ai_scan_completed"] is False

    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "bible_suggestions.json").write_text(
        json.dumps({"groups": [{"section": "themes", "members": []}, {"section": "themes", "members": []}]}),
        encoding="utf-8",
    )
    (dedup_dir / "suggestions.json").write_text(
        json.dumps({"characters": [{"kind": "character", "members": []}], "plot_threads": []}),
        encoding="utf-8",
    )

    bible_status = c.get("/api/projects/p/story-bible/duplicates/status")
    assert bible_status.json()["ai_suggestions_ready"] is True
    assert bible_status.json()["ai_group_count"] == 2

    entity_status = c.get("/api/projects/p/duplicates/status")
    assert entity_status.json()["ai_suggestions_ready"] is True
    assert entity_status.json()["ai_group_count"] == 1
    assert entity_status.json()["has_ai_file"] is True


def test_entity_ai_scan_empty_results_load_as_ai(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    dedup_dir = tmp_path / "p" / "outputs" / "dedup"
    dedup_dir.mkdir(parents=True)
    (dedup_dir / "suggestions.json").write_text(
        json.dumps({
            "scanned_at": "2026-06-29T12:00:00+00:00",
            "characters": [],
            "plot_threads": [],
        }),
        encoding="utf-8",
    )
    c = _client(tmp_path)

    status = c.get("/api/projects/p/duplicates/status").json()
    assert status["has_ai_file"] is True
    assert status["ai_scan_completed"] is True
    assert status["ai_suggestions_ready"] is False

    report = c.get("/api/projects/p/duplicates?ai=true").json()
    assert report["source"] == "ai"
    assert report["ai_scan_completed"] is True
    assert report["characters"] == []
    assert report["plot_threads"] == []


def test_project_backup_lifecycle(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {
        "char_a": {
            "id": "char_a", "full_name": "Alice", "role": "protagonist",
            "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
        }
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)

    assert c.get("/api/projects/p/backups").status_code == 200
    assert c.post("/api/projects/p/backups/quick-save").status_code == 200

    data["characters"]["char_b"] = {
        "id": "char_b", "full_name": "Bob", "role": "supporting",
        "relationships": {}, "knowledge": [], "possessions": [], "aliases": [],
    }
    sf.write_text(json.dumps(data), encoding="utf-8")

    r = c.post("/api/projects/p/backups", json={"label": "With Alice only"})
    assert r.status_code == 201
    backup_id = r.json()["id"]

    listed = c.get("/api/projects/p/backups").json()
    assert any(b["id"] == backup_id for b in listed["named"])
    assert listed["quick"]["current"] is not None

    restore = c.post("/api/projects/p/backups/quick-restore")
    assert restore.status_code == 200
    chars = c.get("/api/projects/p/characters").json()
    assert len(chars) == 1
    assert chars[0]["full_name"] == "Alice"

    undo = c.post("/api/projects/p/backups/undo-restore")
    assert undo.status_code == 200
    chars2 = c.get("/api/projects/p/characters").json()
    assert len(chars2) == 2

    assert c.delete(f"/api/projects/p/backups/{backup_id}").status_code == 204
    assert c.get("/api/projects/p/backups").json()["named"] == []


def test_generate_outline_lifecycle(tmp_path, monkeypatch):
    from chapter_outline_generator import ChapterOutlineGenerator

    _seed_with_chapter(tmp_path, draft="Chapter prose about Jordan and the archive.")
    proj = tmp_path / "p" / "outputs"
    outline = proj / "chapter_001_outline.md"

    def fake_generate(self, number, *, source="draft", instructions="", dry_run=False, on_progress=None):
        preview = "# Chapter 1: The Archive\n\n## Beats\n1. **Opening** — Jordan enters."
        self.preview_path(number).parent.mkdir(parents=True, exist_ok=True)
        self.preview_path(number).write_text(preview, encoding="utf-8")
        self.meta_path(number).write_text(
            '{"source":"draft","original_word_count":6,"preview_word_count":8,"generated_at":"now"}',
            encoding="utf-8",
        )
        return preview, "/tmp/report.md"

    monkeypatch.setattr(ChapterOutlineGenerator, "generate", fake_generate)
    c = _client(tmp_path)

    r = c.post("/api/projects/p/chapters/1/generate-outline", json={"source": "draft"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    import time
    for _ in range(30):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            break
        time.sleep(0.05)
    assert j["status"] == "done"

    prev = c.get("/api/projects/p/chapters/1/generate-outline/preview")
    assert prev.status_code == 200
    assert "Beats" in prev.json()["text"]

    applied = c.post("/api/projects/p/chapters/1/generate-outline/apply", json={
        "text": prev.json()["text"],
    })
    assert applied.status_code == 200
    assert applied.json()["target"] == "outline"
    assert outline.exists()
    assert "Jordan" in outline.read_text(encoding="utf-8")
    assert c.get("/api/projects/p/chapters/1/generate-outline/preview").status_code == 404


def test_generate_outline_from_notes_requires_instructions(tmp_path):
    _seed_with_chapter(tmp_path)
    c = _client(tmp_path)
    r = c.post("/api/projects/p/chapters/1/generate-outline", json={"source": "notes"})
    assert r.status_code == 400


def test_plot_panel_issues_api(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["plot_threads"] = {
        "plot_a": {
            "id": "plot_a", "name": "Main arc", "description": "", "thread_type": "main",
            "status": "active", "priority": 5, "sort_order": 0,
            "subplots": ["Heist planning: crew meets"],
        },
        "plot_b": {
            "id": "plot_b", "name": "B plot", "description": "", "thread_type": "main",
            "status": "active", "priority": 3, "sort_order": 1,
            "subplots": ["Heist planning: the crew gathers"],
        },
    }
    sf.write_text(json.dumps(data), encoding="utf-8")
    c = _client(tmp_path)
    report = c.get("/api/projects/p/plot-threads/panel-issues")
    assert report.status_code == 200
    issues = report.json()["issues"]
    assert len(issues) >= 1
    issue_id = issues[0]["issue_id"]
    resolved = c.post(
        "/api/projects/p/plot-threads/panel-issues/resolve",
        json={"issue_id": issue_id},
    )
    assert resolved.status_code == 200
    assert resolved.json()["log"]
