"""Codex auto-extraction: deterministic candidates, LLM classification, accept/dismiss."""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from server import llm
from server.agents import extract as ex
from server.db import engine
from server.models import Chapter, CodexEntry, Memory

CH1 = ("Iris Vane walked to Saltmarsh Abbey at dawn. Brother Tomas waited by the gate. "
       "\"You came,\" said Tomas. Iris Vane nodded.")
CH2 = "Later, Tomas led her through Saltmarsh Abbey. The bells of Saltmarsh Abbey rang. Iris Vane listened."


@pytest.fixture(autouse=True)
def sync_jobs(monkeypatch):
    monkeypatch.setattr(ex, "SYNC", True)
    monkeypatch.setenv("NOVEL_OS_NO_EMBED", "1")


def fake_llm(monkeypatch, reply_for):
    calls = []

    def complete(session, system, user, *, agent=None, max_tokens=None):
        calls.append(user)
        return json.dumps(reply_for(user)), llm.Route("fake", "fake-1"), "fake-1"

    monkeypatch.setattr(llm, "complete", complete)
    return calls


def echo_all(user):
    """Classify every candidate listed in the prompt."""
    names = [line[2:].split(" (seen")[0] for line in user.split("## Candidates\n", 1)[1].splitlines()
             if line.startswith("- ")]
    out = []
    for n in names:
        out.append({"name": n, "kind": "location" if "Abbey" in n else "character", "summary": f"{n} summary.",
                    "first_chapter": 1, "evidence_quote": "Brother Tomas waited by the gate." if n == "Tomas"
                    else "not in the text at all"})
    return out + [{"name": "Invented", "kind": "item", "summary": "x", "first_chapter": 1, "evidence_quote": ""}]


def seed(pid):
    with Session(engine()) as s:
        s.add(Chapter(project_id=pid, number=1, title="One", text=CH1, word_count=20))
        s.add(Chapter(project_id=pid, number=2, title="Two", text=CH2, word_count=20))
        s.commit()


def base(pid):
    return f"/api/projects/{pid}/codex/proposals"


def test_candidates_exclude_codex_names_and_aliases(client, project):
    pid = project["id"]
    seed(pid)
    client.post(f"/api/projects/{pid}/codex", json={"kind": "character", "name": "Brother T",
                                                    "aliases": ["Tomas"]})
    with Session(engine()) as s:
        names = {c["name"] for c in ex.candidates(s, pid)}
    assert "Iris Vane" in names and "Saltmarsh Abbey" in names
    assert "Tomas" not in names


def test_run_creates_proposals_with_verbatim_evidence(client, project, monkeypatch):
    pid = project["id"]
    seed(pid)
    fake_llm(monkeypatch, echo_all)
    r = client.post(base(pid), json={})
    assert r.status_code == 202 and r.json()["run_id"]
    got = {p["name"]: p for p in client.get(base(pid)).json()}
    assert "Invented" not in got
    assert got["Tomas"]["evidence"] == "Brother Tomas waited by the gate."
    assert got["Saltmarsh Abbey"]["kind"] == "location"
    for p in got.values():
        assert p["evidence"] == "" or p["evidence"] in CH1 + CH2
        assert len(p["evidence"]) <= 200


def test_accept_creates_entry_and_memory(client, project, monkeypatch):
    pid = project["id"]
    seed(pid)
    fake_llm(monkeypatch, echo_all)
    client.post(base(pid), json={})
    prop = next(p for p in client.get(base(pid)).json() if p["name"] == "Tomas")
    r = client.post(f"{base(pid)}/{prop['id']}/accept")
    assert r.status_code == 200
    with Session(engine()) as s:
        e = s.exec(select(CodexEntry).where(CodexEntry.project_id == pid, CodexEntry.name == "Tomas")).one()
        assert e.summary == "Tomas summary." and e.first_chapter == 1 and e.kind == "character"
        mems = s.exec(select(Memory).where(Memory.project_id == pid, Memory.kind == "fact")).all()
        assert any("Tomas" in m.content and m.agent_id is None for m in mems)
    assert all(p["name"] != "Tomas" for p in client.get(base(pid)).json())
    assert client.post(f"{base(pid)}/{prop['id']}/accept").status_code == 409


def test_dismissed_name_not_reproposed(client, project, monkeypatch):
    pid = project["id"]
    seed(pid)
    fake_llm(monkeypatch, echo_all)
    client.post(base(pid), json={})
    props = client.get(base(pid)).json()
    for p in props:
        assert client.post(f"{base(pid)}/{p['id']}/dismiss").json()["status"] == "dismissed"
    assert client.get(base(pid)).json() == []
    calls = fake_llm(monkeypatch, echo_all)
    client.post(base(pid), json={})
    assert client.get(base(pid)).json() == []
    assert calls == []  # nothing left to classify, so no model call
