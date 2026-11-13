"""Agents area: cast, memory ranking, the writers' room, handoffs, drafting."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from server import llm
from server.agents import memory as mem
from server.agents import runtime
from server.db import engine
from server.models import Chapter, ChapterVersion, Memory, Message, Run
from server.models.base import now


@pytest.fixture(autouse=True)
def sync_jobs(monkeypatch):
    monkeypatch.setattr(runtime, "SYNC", True)
    monkeypatch.setenv("NOVEL_OS_NO_EMBED", "1")


def fake_llm(monkeypatch, reply):
    calls = []

    def complete(session, system, user, *, agent=None, max_tokens=None):
        calls.append({"system": system, "user": user, "agent": agent.name if agent else None})
        text = reply(system, user, agent) if callable(reply) else reply
        return text, llm.Route("fake", "fake-1"), "fake-1"

    def complete_streaming(session, system, user, *, on_text, agent=None, max_tokens=None):
        text, route, model = complete(session, system, user, agent=agent, max_tokens=max_tokens)
        for i in range(1, len(text) + 1, max(1, len(text) // 4)):  # a few chunks, like a real stream
            on_text(text[:i])
        on_text(text)
        return text, route, model

    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(llm, "complete_streaming", complete_streaming)
    return calls


def add_chapter(pid, n=1, **kw):
    with Session(engine()) as s:
        ch = Chapter(project_id=pid, number=n, title=kw.pop("title", f"Ch {n}"), **kw)
        s.add(ch)
        s.commit()
        return ch.id


def agents_by_name(client, pid):
    return {a["name"]: a for a in client.get(f"/api/projects/{pid}/agents").json()}


def messages(client, pid, tid):
    return client.get(f"/api/projects/{pid}/threads/{tid}/messages").json()


def test_cast_is_seeded_once_and_editable(client, project):
    pid = project["id"]
    cast = client.get(f"/api/projects/{pid}/agents").json()
    assert [a["name"] for a in cast] == ["Architect", "Scribe", "Editor", "Guardian", "Curator", "Researcher"]
    assert len(client.get(f"/api/projects/{pid}/agents").json()) == 6
    r = client.post(f"/api/projects/{pid}/agents", json={"role": "scribe", "name": "Scribe · Iris chapters"})
    assert r.status_code == 201
    iris = r.json()
    r = client.patch(f"/api/projects/{pid}/agents/{iris['id']}",
                     json={"autonomy": "autopilot", "temperature": 0.9, "model": "qwen3", "provider": "ollama"})
    assert r.json()["autonomy"] == "autopilot" and r.json()["model_line"] == "ollama · qwen3"
    add_chapter(pid, 2)
    r = client.put(f"/api/projects/{pid}/chapters/2/assignee", json={"agent_id": iris["id"]})
    assert r.status_code == 200
    assert agents_by_name(client, pid)["Scribe · Iris chapters"]["chapters"] == [2]
    assert client.delete(f"/api/projects/{pid}/agents/{iris['id']}").status_code == 204
    assert len(client.get(f"/api/projects/{pid}/agents").json()) == 6


def test_recall_ranks_pinned_and_relevant_first(client, project):
    pid = project["id"]
    with Session(engine()) as s:
        for i in range(8):
            mem.remember(s, pid, "fact", f"The weather in chapter {i} was grey and unremarkable.", importance=0.5)
        rel = mem.remember(s, pid, "fact", "Iris keeps a brass key to the glass orchard greenhouse.", chapter=3)
        pin = mem.remember(s, pid, "preference", "Never use the word suddenly.", pinned=True)
        old = mem.remember(s, pid, "fact", "Old note about orchards.", importance=0.1)
        old.created_at = now() - timedelta(days=400)
        s.add(old)
        s.commit()
        got = mem.recall(s, pid, "Where is the key to the orchard greenhouse?", chapter=3, k=5)
        ids = [m.id for m in got]
        assert ids[0] == pin.id
        assert ids[1] == rel.id
        s.refresh(rel)
        assert rel.recall_count == 1 and rel.last_recalled_at is not None
    # endpoints: list, search, patch, delete
    lst = client.get(f"/api/projects/{pid}/memory", params={"q": "brass key"}).json()
    assert lst[0]["id"] == rel.id
    r = client.patch(f"/api/projects/{pid}/memory/{rel.id}", json={"pinned": True, "importance": 2})
    assert r.json()["pinned"] is True and r.json()["importance"] == 1.0
    assert client.post(f"/api/projects/{pid}/memory", json={"kind": "decision", "content": "Act two ends in snow."}
                       ).status_code == 201
    assert len(client.get(f"/api/projects/{pid}/memory", params={"kind": "decision"}).json()) == 1
    assert client.delete(f"/api/projects/{pid}/memory/{rel.id}").status_code == 204


def test_author_mention_gets_reply(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1, synopsis="Iris finds the key.")
    with Session(engine()) as s:
        mem.remember(s, pid, "fact", "Iris is afraid of wasps.")
    calls = fake_llm(monkeypatch, "Wasps in the orchard would raise the stakes for Iris.")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    r = client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Scribe what scares Iris about wasps?"})
    assert r.status_code == 201 and len(r.json()["runs"]) == 1
    assert calls[0]["agent"] == "Scribe" and "Iris is afraid of wasps" in calls[0]["user"]
    msgs = messages(client, pid, tid)
    assert msgs[0]["sender"] == "author"
    assert msgs[1]["sender"].startswith("agent:") and "Wasps" in msgs[1]["body"]
    with Session(engine()) as s:
        run = s.get(Run, r.json()["runs"][0])
        assert run.status == "done" and run.model == "fake-1" and run.tokens_in > 0
        assert s.exec(select(Memory).where(Memory.kind == "episode")).first() is not None
    # "Remember this" on an author rule
    rule = client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "Iris never swears."}).json()
    r = client.post(f"/api/projects/{pid}/threads/{tid}/messages/{rule['message']['id']}/actions/remember")
    assert r.status_code == 200
    prefs = client.get(f"/api/projects/{pid}/memory", params={"kind": "preference"}).json()
    assert prefs[0]["content"] == "Iris never swears."


def test_handoff_under_autopilot_runs_second_agent(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)
    cast = agents_by_name(client, pid)
    client.patch(f"/api/projects/{pid}/agents/{cast['Scribe']['id']}", json={"autonomy": "autopilot"})

    def reply(system, user, agent):
        if agent.name == "Architect":
            return "The midpoint needs a reversal.\nHANDOFF @Scribe: sketch the reversal scene in a paragraph"
        return "Here is the reversal: the key does not fit."

    fake_llm(monkeypatch, reply)
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Architect does the midpoint work?"})
    msgs = messages(client, pid, tid)
    hand = [m for m in msgs if m["intent"] == "handoff"]
    assert len(hand) == 1 and hand[0]["recipients"] == [cast["Scribe"]["id"]] and hand[0]["actions"] == []
    with Session(engine()) as s:
        runs = s.exec(select(Run).order_by(Run.created_at)).all()
        assert [r.agent_id for r in runs] == [cast["Architect"]["id"], cast["Scribe"]["id"]]
        assert runs[1].input["hops"] == 1
    assert any("key does not fit" in m["body"] for m in msgs)


def test_handoff_under_ask_waits_for_approval(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)
    fake_llm(monkeypatch, lambda s, u, a: "HANDOFF @Editor: look at the opening" if a.name == "Architect" else "ok")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Architect thoughts?"})
    hand = [m for m in messages(client, pid, tid) if m["intent"] == "handoff"][0]
    assert [a["action"] for a in hand["actions"]] == ["run", "dismiss"]
    r = client.post(f"/api/projects/{pid}/threads/{tid}/messages/{hand['id']}/actions/run")
    assert r.status_code == 200 and len(r.json()["runs"]) == 1


def test_handoff_chain_is_capped(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)
    client.put(f"/api/projects/{pid}/agents-autonomy", json={"autonomy": "autopilot"})
    fake_llm(monkeypatch, lambda s, u, a: "Over to you.\nHANDOFF @Researcher: what do you think?"
             if a.name == "Architect" else "Over to you.\nHANDOFF @Architect: what do you think?")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Architect go"})
    with Session(engine()) as s:
        assert len(s.exec(select(Run)).all()) == 1 + runtime.MAX_HOPS
    msgs = messages(client, pid, tid)
    assert any(m["sender"] == "system" and "stopped" in m["body"] for m in msgs)


DRAFT = """<!-- CHAPTER: 1 | TITLE: Frost -->
Iris walked the orchard at dawn. The glass trees rang in the wind.

She found the brass key under the third tree.

[SCRIBE_STATE_UPDATE]
Characters_Present:
  - Iris Vale
Key_Events:
  - Iris finds the brass key
Emotional_Shifts:
  - Iris Vale: wary
New_Information_Revealed:
  - The brass key was buried under the third glass tree
Foreshadowing_Planted:
  - [None]
Foreshadowing_Resolved:
  - [None]
[/SCRIBE_STATE_UPDATE]
"""


def test_draft_writes_text_version_and_facts(client, project, monkeypatch):
    pid = project["id"]
    chid = add_chapter(pid, 1, synopsis="Iris finds the key.")
    fake_llm(monkeypatch, DRAFT)
    r = client.post(f"/api/projects/{pid}/chapters/1/tasks/draft")
    assert r.status_code == 202
    with Session(engine()) as s:
        ch = s.get(Chapter, chid)
        assert ch.status == "drafted" and ch.text.startswith("Iris walked")
        assert "SCRIBE_STATE_UPDATE" not in ch.text and ch.word_count > 10
        v = s.exec(select(ChapterVersion).where(ChapterVersion.chapter_id == chid)).one()
        assert v.kind == "draft" and v.produced_by.startswith("agent:") and v.model == "fake-1"
        facts = [m.content for m in s.exec(select(Memory).where(Memory.kind == "fact")).all()]
        assert "The brass key was buried under the third glass tree" in facts
    st = client.get(f"/api/projects/{pid}/chapters/1/agent-status").json()
    assert next(x for x in st["stages"] if x["task"] == "draft")["status"] == "done"
    assert st["context"]["tokens"] > 0


def test_edit_proposal_accept_and_check_objection(client, project, monkeypatch):
    pid = project["id"]
    chid = add_chapter(pid, 1, text="Old text here.")

    def reply(system, user, agent):
        if agent.role == "editor":
            return "[REVISED_CHAPTER]\nNew text here.\n[/REVISED_CHAPTER]\n[EDITOR_STATE_UPDATE]\nImprovements_Made:\n  - tighter\n[/EDITOR_STATE_UPDATE]"
        return ("[CONTINUITY_REPORT]\nStatus: FAIL\nCritical_Issues:\n  - Iris is in two places -> move her\n"
                "Warnings:\n  - [None]\n[/CONTINUITY_REPORT]")

    fake_llm(monkeypatch, reply)
    client.post(f"/api/projects/{pid}/chapters/1/tasks/edit")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    prop = [m for m in messages(client, pid, tid) if m["intent"] == "proposal"][0]
    with Session(engine()) as s:
        assert s.get(Chapter, chid).text == "Old text here."
    client.post(f"/api/projects/{pid}/threads/{tid}/messages/{prop['id']}/actions/accept")
    with Session(engine()) as s:
        assert s.get(Chapter, chid).text == "New text here."
    client.post(f"/api/projects/{pid}/chapters/1/tasks/check")
    st = client.get(f"/api/projects/{pid}/chapters/1/agent-status").json()
    assert "two places" in st["objection"]["body"]
    assert [a["label"] for a in st["objection"]["actions"]] == ["Fix in text", "This is intentional"]


def test_pipeline_runs_all_steps(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)

    def reply(system, user, agent):
        return {"architect": "SYNOPSIS: Iris digs.\nBEATS:\n- dawn\n- key", "scribe": DRAFT,
                "editor": "[REVISED_CHAPTER]\nEdited.\n[/REVISED_CHAPTER]"}.get(
            agent.role, "[CONTINUITY_REPORT]\nStatus: PASS\n[/CONTINUITY_REPORT]")

    fake_llm(monkeypatch, reply)
    assert client.post(f"/api/projects/{pid}/chapters/1/pipeline").status_code == 202
    with Session(engine()) as s:
        assert [r.task for r in s.exec(select(Run).order_by(Run.created_at)).all()] == ["plan", "draft", "edit", "check"]
        assert s.exec(select(Message).where(Message.intent == "handoff")).all()


def test_author_rulings_bind_every_agent_regardless_of_recall(client, project, monkeypatch):
    """Regression: the Editor 'fixed' a knife the author had marked intentional,
    because decisions only reached agents when ranked recall happened to pick them."""
    pid = project["id"]
    add_chapter(pid, 3, text="The grafting knife lay on the sill.", synopsis="The valuer walks the orchard.")
    with Session(engine()) as s:
        mem.remember(s, pid, "decision", "Intentional: the knife on the sill in ch 3 is a second knife.")
        mem.remember(s, pid, "preference", "Iris never swears.")
        for i in range(40):  # bury them under unrelated, more 'relevant' memories
            mem.remember(s, pid, "fact", f"The valuer walks the orchard on visit {i}.", importance=0.9)
        s.commit()
    calls = fake_llm(monkeypatch, "Tightened.")
    editor = agents_by_name(client, pid)["Editor"]
    assert client.post(f"/api/projects/{pid}/agents/{editor['id']}/run",
                       json={"task": "edit", "chapter": 3}).status_code in (200, 201, 202)
    system = calls[0]["system"]
    assert "Author rulings (binding)" in system
    assert "second knife" in system and "Iris never swears" in system
    assert "second knife" not in calls[0]["user"]  # not duplicated in the recall section


def test_chat_reply_streams_into_one_message(client, project, monkeypatch):
    from server import events
    from server.agents import runtime as rt
    pid = project["id"]
    add_chapter(pid, 1)
    monkeypatch.setattr(rt, "STREAM_EVERY_S", 0)
    published = []
    monkeypatch.setattr(events, "publish", lambda p, t, d=None: published.append((t, d or {})))
    fake_llm(monkeypatch, "Iris would say less, and mean more.\nHANDOFF @Editor: tighten it")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Scribe a line for Iris?"})

    deltas = [d for t, d in published if t == "message.delta"]
    assert len(deltas) >= 2, "reply should arrive in pieces"
    assert all("HANDOFF" not in d["body"] for d in deltas), "routing lines never shown mid-stream"
    msgs = messages(client, pid, tid)
    scribe = [m for m in msgs if m["sender"].startswith("agent:") and m["intent"] == "note"]
    assert len(scribe) == 1 and scribe[0]["body"] == "Iris would say less, and mean more."
    assert deltas[-1]["id"] == scribe[0]["id"]


# ---- per-book agent controls -------------------------------------------------------------

def test_custom_agent_chats_with_its_brief(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)
    r = client.post(f"/api/projects/{pid}/agents",
                    json={"role": "custom", "name": "Tomas", "brief": "Never use semicolons."})
    assert r.status_code == 201 and r.json()["role"] == "custom"
    assert client.post(f"/api/projects/{pid}/agents", json={"role": "wizard", "name": "X"}).status_code == 422
    calls = fake_llm(monkeypatch, "Short and plain.")
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Tomas a line?"})
    assert calls and calls[0]["agent"] == "Tomas"
    assert "Never use semicolons." in calls[0]["system"]
    assert "helpful member of a novel-writing team" not in calls[0]["system"]  # built on the scribe prompt
    assert any(m["body"] == "Short and plain." for m in messages(client, pid, tid))


def test_patch_brief_model_temperature_reach_prompt_and_route(client, project, monkeypatch):
    from server.models import Agent
    pid = project["id"]
    add_chapter(pid, 1)
    scribe = agents_by_name(client, pid)["Scribe"]
    r = client.patch(f"/api/projects/{pid}/agents/{scribe['id']}",
                     json={"brief": "Write Iris's chapters; terse.", "provider": "ollama", "model": "qwen3",
                           "temperature": 1.2})
    assert r.json()["model_line"] == "ollama · qwen3" and r.json()["route_provider"] == "ollama"
    with Session(engine()) as s:
        route = llm.resolve(s, s.get(Agent, scribe["id"]))
        assert route.provider == "ollama" and route.model == "qwen3" and route.temperature == 1.2
    calls = fake_llm(monkeypatch, DRAFT)
    client.post(f"/api/projects/{pid}/agents/{scribe['id']}/run", json={"task": "draft", "chapter": 1})
    assert "Write Iris's chapters; terse." in calls[0]["system"]


def test_pipeline_draft_uses_assigned_agent(client, project, monkeypatch):
    pid = project["id"]
    add_chapter(pid, 1)
    tomas = client.post(f"/api/projects/{pid}/agents", json={"role": "scribe", "name": "Scribe · Tomas"}).json()
    client.put(f"/api/projects/{pid}/chapters/1/assignee", json={"agent_id": tomas["id"]})

    def reply(system, user, agent):
        return {"architect": "SYNOPSIS: x\nBEATS:\n- a", "scribe": DRAFT,
                "editor": "[REVISED_CHAPTER]\nEdited.\n[/REVISED_CHAPTER]"}.get(
            agent.role, "[CONTINUITY_REPORT]\nStatus: PASS\n[/CONTINUITY_REPORT]")

    fake_llm(monkeypatch, reply)
    client.post(f"/api/projects/{pid}/chapters/1/pipeline")
    with Session(engine()) as s:
        draft = s.exec(select(Run).where(Run.task == "draft")).one()
        assert draft.agent_id == tomas["id"]


def test_last_core_agent_cannot_be_deleted(client, project):
    pid = project["id"]
    cast = agents_by_name(client, pid)
    assert client.delete(f"/api/projects/{pid}/agents/{cast['Editor']['id']}").status_code == 409
    extra = client.post(f"/api/projects/{pid}/agents", json={"role": "editor", "name": "Editor two"}).json()
    assert client.delete(f"/api/projects/{pid}/agents/{cast['Editor']['id']}").status_code == 204
    assert client.delete(f"/api/projects/{pid}/agents/{extra['id']}").status_code == 409


def test_cancel_queued_run(client, project):
    from server import jobs
    pid = project["id"]
    with Session(engine()) as s:
        run = Run(project_id=pid, task="draft", chapter=1)
        s.add(run)
        s.commit()
        rid = run.id
    r = client.post(f"/api/projects/{pid}/runs/{rid}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    ran = []
    jobs._execute(rid, pid, lambda _rid: ran.append(1) or {})  # noqa: SLF001 - a worker picks it up late
    assert not ran
    assert client.get(f"/api/projects/{pid}/runs/{rid}").json()["status"] == "cancelled"


def test_cancel_mid_stream_keeps_partial_reply(client, project, monkeypatch):
    from server import jobs
    pid = project["id"]
    add_chapter(pid, 1)
    after_cancel = []

    def complete_streaming(session, system, user, *, on_text, agent=None, max_tokens=None):
        words = "Iris stood at the gate and looked back at the orchard for a long time".split()
        text = ""
        for i, w in enumerate(words):
            text += ("" if not text else " ") + w
            if i == 4:  # the author presses Stop mid-reply
                rid = session.exec(select(Run.id).where(Run.status == "running", Run.task == "chat")).first()
                jobs.request_cancel(rid)
            if i > 4:
                after_cancel.append(w)
            on_text(text)
        return text, llm.Route("fake", "fake-1"), "fake-1"

    monkeypatch.setattr(llm, "complete_streaming", complete_streaming)
    tid = client.get(f"/api/projects/{pid}/chapters/1/thread").json()["id"]
    client.post(f"/api/projects/{pid}/threads/{tid}/messages", json={"body": "@Scribe a line?"})
    assert after_cancel == [], "the stream stops at the next chunk"
    with Session(engine()) as s:
        assert s.exec(select(Run).where(Run.task == "chat")).one().status == "cancelled"
    reply = [m for m in messages(client, pid, tid) if m["sender"].startswith("agent:")]
    assert len(reply) == 1
    assert reply[0]["body"].startswith("Iris stood at the gate") and reply[0]["body"].endswith("(stopped)")
