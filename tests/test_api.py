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
    assert rows[0]["pov"] == "Lena"


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


def test_save_final_404_for_missing_chapter(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    assert _client(tmp_path).put("/api/projects/p/chapters/9/final",
                                 json={"text": "x"}).status_code == 404


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
