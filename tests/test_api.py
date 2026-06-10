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
    app = create_app(projects_root=projects_root)
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
