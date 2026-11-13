"""Inline Editor suggestions: generation, validation, accept/dismiss."""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from server import llm
from server.agents import suggest as sg
from server.db import engine
from server.models import Chapter, ChapterVersion, Memory

TEXT = ("Iris walked very slowly across the old wooden bridge. The river below was loud and angry. "
        "She really, truly did not want to look down at the water.")


@pytest.fixture(autouse=True)
def sync_jobs(monkeypatch):
    monkeypatch.setattr(sg, "SYNC", True)
    monkeypatch.setenv("NOVEL_OS_NO_EMBED", "1")


def fake_llm(monkeypatch, items):
    calls = []

    def complete(session, system, user, *, agent=None, max_tokens=None):
        calls.append({"system": system, "user": user})
        return "```json\n" + json.dumps(items) + "\n```", llm.Route("fake", "fake-1"), "fake-1"

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def add_chapter(pid, n=1, text=TEXT):
    with Session(engine()) as s:
        s.add(Chapter(project_id=pid, number=n, title="Bridge", text=text, word_count=len(text.split())))
        s.commit()


GOOD = [
    {"quote": "walked very slowly", "replacement": "crept", "reason": "Stronger verb.", "kind": "tighten"},
    {"quote": "She really, truly did not want", "replacement": "She did not want", "reason": "Adverbs.",
     "kind": "tighten"},
]


def base(pid, n=1):
    return f"/api/projects/{pid}/chapters/{n}/suggestions"


def run(client, pid, items, monkeypatch, focus=""):
    calls = fake_llm(monkeypatch, items)
    r = client.post(base(pid), json={"focus": focus})
    assert r.status_code == 202 and r.json()["run_id"]
    return calls


def test_invalid_quotes_dropped(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    run(client, pid, GOOD + [
        {"quote": "a sentence that is not there", "replacement": "x", "reason": "", "kind": "clarity"},
        {"quote": "very slowly across the", "replacement": "slowly over the", "reason": "overlap", "kind": "tighten"},
        {"quote": "The river", "replacement": "It", "reason": "too short", "kind": "clarity"},
    ], monkeypatch)
    got = client.get(base(pid)).json()
    assert [g["quote"] for g in got] == [GOOD[0]["quote"], GOOD[1]["quote"]]
    assert all(g["status"] == "open" for g in got)


def test_accept_replaces_text_and_versions(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    run(client, pid, GOOD, monkeypatch)
    sid = client.get(base(pid)).json()[0]["id"]
    r = client.post(f"{base(pid)}/{sid}/accept")
    assert r.status_code == 200
    ch = r.json()
    assert "Iris crept across" in ch["text"]
    assert ch["word_count"] == len(ch["text"].split())
    assert ch["doc"] == {}
    with Session(engine()) as s:
        vs = s.exec(select(ChapterVersion)).all()
        assert any(v.kind == "edit" and v.note == "Accepted suggestion" and v.produced_by.startswith("agent:")
                   for v in vs)
    assert len(client.get(base(pid)).json()) == 1


def test_accept_conflict_after_edit(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    run(client, pid, GOOD, monkeypatch)
    sid = client.get(base(pid)).json()[0]["id"]
    client.patch(f"/api/projects/{pid}/chapters/1", json={"text": "Iris ran across the bridge. Done."})
    assert client.post(f"{base(pid)}/{sid}/accept").status_code == 409


def test_dismiss_creates_preference(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    run(client, pid, GOOD, monkeypatch)
    sid = client.get(base(pid)).json()[0]["id"]
    r = client.post(f"{base(pid)}/{sid}/dismiss")
    assert r.status_code == 200 and r.json()["status"] == "dismissed"
    with Session(engine()) as s:
        m = s.exec(select(Memory).where(Memory.kind == "style")).all()
        assert any("Author rejected an edit: 'walked very slowly' → 'crept'" in x.content for x in m)
        assert m[0].importance == pytest.approx(0.4)
    assert len(client.get(base(pid)).json()) == 1


def test_accept_all(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    run(client, pid, GOOD, monkeypatch)
    r = client.post(f"{base(pid)}/accept-all")
    assert r.status_code == 200
    text = r.json()["text"]
    assert "Iris crept across" in text and "She did not want" in text
    assert client.get(base(pid)).json() == []


def test_rulings_reach_system_prompt(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid)
    client.post(f"/api/projects/{pid}/memory", json={"kind": "decision", "content": "Iris always walks slowly."})
    calls = run(client, pid, [], monkeypatch, focus="less adverbs")
    assert "Author rulings (binding)" in calls[0]["system"]
    assert "Iris always walks slowly." in calls[0]["system"]
    assert "less adverbs" in calls[0]["user"]
