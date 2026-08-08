"""Styles and compile over the wire (P5.2 / P6)."""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

CH1 = "She waited at the rail.\n\nThe tide came in.\n\n---\n\nHe did not come.\n"
CH2 = "They left before dawn.\n"


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "manuscript").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "The Pier", "genre": "Literary", "author": "M"},
        "characters": {}, "plot_threads": {},
        "chapters": {
            "1": {"number": 1, "title": "Arrival", "status": "drafted"},
            "2": {"number": 2, "title": "Departure", "status": "drafted"},
        },
        "timeline": [], "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    ms = proj / "outputs" / "manuscript"
    (ms / "chapter_001_final.md").write_text(CH1, encoding="utf-8")
    (ms / "chapter_002_final.md").write_text(CH2, encoding="utf-8")
    app = create_app(projects_root=root,
                     db_url=f"sqlite:///{(tmp_path / 'c.db').as_posix()}")
    return TestClient(app)


# ------------------------------------------------------------------ styles

def test_styles_come_back_with_defaults_filled_in(client):
    body = client.get("/api/projects/book/styles").json()
    assert body["scene_break_marker"] == "* * *"
    assert body["styles"]["chapter_title"]["bold"] is True
    assert body["styles"]["body"]["first_line_indent_em"] > 0


def test_saving_styles_persists_them(client):
    body = client.get("/api/projects/book/styles").json()
    body["styles"]["body"]["size_pt"] = 13.5
    body["scene_break_marker"] = "~ ~ ~"

    assert client.put("/api/projects/book/styles", json=body).status_code == 200

    again = client.get("/api/projects/book/styles").json()
    assert again["styles"]["body"]["size_pt"] == 13.5
    assert again["scene_break_marker"] == "~ ~ ~"


def test_a_nonsense_stylesheet_is_rejected_whole(client):
    body = client.get("/api/projects/book/styles").json()
    body["styles"]["body"]["size_pt"] = 400

    r = client.put("/api/projects/book/styles", json=body)
    assert r.status_code == 400
    assert "size" in r.json()["detail"]

    # Nothing was written: the good value is still there.
    assert client.get("/api/projects/book/styles").json()[
        "styles"]["body"]["size_pt"] == 12.0


def test_styles_404_for_an_unknown_project(client):
    assert client.get("/api/projects/nope/styles").status_code == 404


# ----------------------------------------------------------------- compile

def test_compile_returns_a_downloadable_html_book(client):
    r = client.get("/api/projects/book/compile?format=html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'filename="book.html"' in r.headers["content-disposition"]
    assert "<title>The Pier</title>" in r.text
    assert "Arrival" in r.text and "Departure" in r.text


def test_compile_walks_every_chapter_in_order(client):
    text = client.get("/api/projects/book/compile?format=html").text
    assert text.index("Arrival") < text.index("Departure")
    assert text.index("She waited") < text.index("They left")


def test_saved_styles_reach_the_compiled_book(client):
    body = client.get("/api/projects/book/styles").json()
    body["styles"]["body"]["size_pt"] = 21
    body["scene_break_marker"] = "~ ~ ~"
    client.put("/api/projects/book/styles", json=body)

    text = client.get("/api/projects/book/compile?format=html").text
    assert "font-size:21pt" in text
    assert "~ ~ ~" in text


def test_markdown_compile_is_offered_too(client):
    r = client.get("/api/projects/book/compile?format=markdown")
    assert r.status_code == 200
    assert 'filename="book.md"' in r.headers["content-disposition"]
    assert r.text.startswith("# The Pier")


def test_an_unknown_format_is_a_400_that_lists_the_options(client):
    r = client.get("/api/projects/book/compile?format=docx")
    assert r.status_code == 400
    assert "html" in r.json()["detail"]


def test_compile_404_for_an_unknown_project(client):
    assert client.get("/api/projects/nope/compile").status_code == 404
