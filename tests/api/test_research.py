"""Research swarm: lifecycle, sources, memories, Codex filing, excerpt cap, robots. No network."""

from __future__ import annotations

import json

import pytest

from server.research import browser, swarm
from server.research import search as search_mod

PAGES = {
    "https://www.si.edu/orchards": browser.Page(
        url="https://www.si.edu/orchards", title="Orchards of the 1890s",
        text="Glasshouses were heated with coal stoves through the winter months. " * 3
             + "Apprentice gardeners earned about four shillings a week.",
    ),
    "https://history.example.org/glass": browser.Page(
        url="https://history.example.org/glass", title="Victorian glass",
        text="Sheet glass became cheap after the repeal of the glass tax in 1845, " + "and more. " * 80,
    ),
    "https://blog.example.com/post": browser.Page(
        url="https://blog.example.com/post", title="Some blog", text="I think orchards are nice.",
    ),
}

LONG_QUOTE = "Sheet glass became cheap after the repeal of the glass tax in 1845, " + "and more. " * 80


def fake_complete(session, system, user, **kw):  # noqa: ANN001
    if system == swarm.PLAN_SYSTEM:
        return json.dumps(["victorian glasshouse heating", "victorian glass tax"]), None, "fake"
    if system == swarm.EXTRACT_SYSTEM:
        if "si.edu" in user:
            return ("Here you go:\n```json\n" + json.dumps([
                {"claim": "Glasshouses were heated by coal stoves in winter.",
                 "excerpt": "Glasshouses were heated with coal stoves through the winter months.",
                 "url": "x", "reliability": 0.9},
                {"claim": "Apprentices earned roughly four shillings weekly.",
                 "excerpt": "Apprentice gardeners earned about four shillings a week.", "reliability": 0.8},
                {"claim": "Fabricated", "excerpt": "This sentence is not on the page.", "reliability": 0.9},
            ]) + "\n```"), None, "fake"
        if "history.example.org" in user:
            return json.dumps([{"claim": "Glass got cheap after the 1845 tax repeal.",
                                "excerpt": LONG_QUOTE, "reliability": 0.7}]), None, "fake"
        return json.dumps([{"claim": "Orchards are nice.", "excerpt": "I think orchards are nice.",
                            "reliability": 0.2}]), None, "fake"
    if system == swarm.SYNTH_SYSTEM:
        return "Coal stoves kept glasshouses warm [1], and glass was cheap after 1845 [3].", None, "fake"
    raise AssertionError(system)


def fake_search(query, n=5):  # noqa: ANN001
    if "heating" in query:
        return [{"title": "Orchards", "url": "https://www.si.edu/orchards", "snippet": ""},
                {"title": "Blog", "url": "https://blog.example.com/post", "snippet": ""}]
    return [{"title": "Glass", "url": "https://history.example.org/glass", "snippet": ""},
            {"title": "Orchards", "url": "https://www.si.edu/orchards", "snippet": ""}]


@pytest.fixture
def swarm_stubs(monkeypatch):
    monkeypatch.setattr(swarm, "SYNC", True)
    monkeypatch.setattr("server.llm.complete", fake_complete)
    monkeypatch.setattr(search_mod, "search", fake_search)
    monkeypatch.setattr(browser, "fetch", lambda url: PAGES[url])


def _start(client, project, **body):
    r = client.post(f"/api/projects/{project['id']}/research",
                    json={"question": "How were Victorian glasshouses heated?", **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_task_lifecycle_to_done(client, project, swarm_stubs):
    task = _start(client, project, chapter=2)
    assert task["status"] == "done"
    assert task["summary"].startswith("Coal stoves")
    urls = {s["url"] for s in task["sources"]}
    assert "https://www.si.edu/orchards" in urls and "https://history.example.org/glass" in urls
    # fabricated (non-verbatim) quotes are dropped
    assert not any(s["note"] == "Fabricated" for s in task["sources"])
    assert len(task["sources"]) == 4
    assert task["sources"][0]["reliability"] == 0.9  # sorted by reliability
    assert task["sources"][0]["domain"] == "si.edu"

    listing = client.get(f"/api/projects/{project['id']}/research").json()
    assert listing["tasks"][0]["source_count"] == 4
    assert listing["sources"] == 4

    detail = client.get(f"/api/projects/{project['id']}/research/{task['id']}").json()
    assert detail["status"] == "done" and len(detail["sources"]) == 4


def test_research_memories_created(client, project, swarm_stubs):
    from sqlmodel import Session, select

    from server.db import engine
    from server.models import Memory

    task = _start(client, project, chapter=2)
    with Session(engine()) as s:
        mems = s.exec(select(Memory).where(Memory.source == f"research:{task['id']}")).all()
    assert len(mems) == 3  # 0.9, 0.8, 0.7 kept; the 0.2 blog post is not a strong finding
    assert all(m.kind == "research" and m.agent_id is None and m.chapter == 2 for m in mems)
    assert sorted(m.importance for m in mems) == [0.7, 0.8, 0.9]


def test_excerpt_cap_enforced(client, project, swarm_stubs):
    task = _start(client, project)
    glass = next(s for s in task["sources"] if "history.example.org" in s["url"])
    assert len(glass["excerpt"]) <= 300
    assert glass["excerpt"].startswith("Sheet glass became cheap")
    assert all(len(s["excerpt"]) <= 300 for s in task["sources"])
    assert len(swarm.cap_excerpt("word " * 200)) <= 300


def test_file_to_codex(client, project, swarm_stubs):
    from sqlmodel import Session

    from server.db import engine
    from server.models import CodexEntry

    task = _start(client, project)
    src = task["sources"][0]
    pid = project["id"]
    r = client.post(f"/api/projects/{pid}/research/sources/{src['id']}/file", json={"name": "Glasshouse"})
    assert r.status_code == 200, r.text
    entry_id = r.json()["filed_to_codex_id"]
    assert entry_id
    # filing a second source by the same name appends to the same entry
    src2 = task["sources"][1]
    r2 = client.post(f"/api/projects/{pid}/research/sources/{src2['id']}/file", json={"name": "glasshouse"})
    assert r2.json()["filed_to_codex_id"] == entry_id
    with Session(engine()) as s:
        e = s.get(CodexEntry, entry_id)
        assert e.name == "Glasshouse"
        assert src["url"] in e.notes and src2["url"] in e.notes
        assert f'"{src["excerpt"]}"' in e.notes


def test_cancel_delete_retry(client, project, swarm_stubs):
    pid = project["id"]
    task = _start(client, project)
    r = client.post(f"/api/projects/{pid}/research/{task['id']}/retry")
    assert r.status_code == 200 and r.json()["status"] == "done" and len(r.json()["sources"]) == 4
    assert client.post(f"/api/projects/{pid}/research/{task['id']}/cancel").json()["status"] == "done"
    assert client.delete(f"/api/projects/{pid}/research/{task['id']}").status_code == 204
    assert client.get(f"/api/projects/{pid}/research/{task['id']}").status_code == 404
    assert client.get(f"/api/projects/{pid}/research/suggestions").status_code == 200


def test_failed_llm_marks_task_failed(client, project, swarm_stubs, monkeypatch):
    def boom(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("no model configured")
    monkeypatch.setattr("server.llm.complete", boom)
    task = _start(client, project)
    assert task["status"] == "failed"
    assert "no model configured" in task["progress"]


# ------------------------------------------------------------------ browser module (unit)

class _Resp:
    def __init__(self, status: int, text: str):
        self.status_code, self.text = status, text


def test_robots_disallow_respected(monkeypatch):
    browser.clear_cache()
    robots = "User-agent: *\nDisallow: /private/\n"
    monkeypatch.setattr(browser.httpx, "get", lambda url, **kw: _Resp(200, robots))
    monkeypatch.setattr(browser, "_playwright_available", lambda: False)
    fetched: list[str] = []
    monkeypatch.setattr(browser, "_fetch_http", lambda url: fetched.append(url) or browser.Page(url=url, text="ok"))

    with pytest.raises(browser.RobotsDisallowed):
        browser.fetch("https://museum.example/private/archive.html")
    assert fetched == []
    assert browser.fetch("https://museum.example/public/page.html").text == "ok"
    assert fetched == ["https://museum.example/public/page.html"]
    browser.clear_cache()


def test_extract_strips_chrome():
    html = """<html><head><title> Orchard  History </title><style>.x{}</style></head><body>
    <nav><a href="/home">Home</a> Menu</nav><script>var a=1;</script>
    <h1>Glasshouses</h1><p>Heated with <b>coal</b>.</p><a href="https://si.edu/x">More</a>
    <footer>Copyright</footer></body></html>"""
    page = browser.extract(html, "https://example.org/a")
    assert page.title == "Orchard History"
    assert "## Glasshouses" in page.text and "Heated with coal." in page.text
    assert "Menu" not in page.text and "var a" not in page.text and "Copyright" not in page.text
    assert "https://si.edu/x" in page.links
    assert len(browser.extract("<p>" + "a " * 30000 + "</p>").text) <= browser.MAX_CHARS


def test_parse_duckduckgo():
    html = ('<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fsi.edu%2Fa&rut=1">'
            'Smithsonian <b>orchards</b></a><a class="result__snippet">Old glass houses</a></div>')
    hits = search_mod.parse_ddg(html)
    assert hits == [{"title": "Smithsonian orchards", "url": "https://si.edu/a", "snippet": "Old glass houses"}]
