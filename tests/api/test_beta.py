"""Beta-reader portal: token isolation, closed rounds, rate limit, insights, memory, summary job."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from server import llm
from server.beta import insights as ins
from server.beta import ratelimit
from server.beta import summarize as summ
from server.db import engine
from server.models import Chapter, Memory, Message, Thread

TEXT = "a" * 1000


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(summ, "SYNC", True)
    monkeypatch.setenv("NOVEL_OS_NO_EMBED", "1")
    ratelimit.reset()
    yield
    ratelimit.reset()


def add_chapters(pid, n=3):
    with Session(engine()) as s:
        for i in range(1, n + 1):
            s.add(Chapter(project_id=pid, number=i, title=f"Ch {i}", text=TEXT, word_count=1))
        s.commit()


def make_round(client, pid, chapters=(1, 2, 3), readers=("Ada", "Ben")):
    add_chapters(pid)
    r = client.post(f"/api/projects/{pid}/beta/rounds", json={"name": "First", "chapters": list(chapters)})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    toks = []
    for name in readers:
        x = client.post(f"/api/projects/{pid}/beta/rounds/{rid}/readers", json={"name": name}).json()
        assert x["link"] == f"/read/{x['token']}" and len(x["token"]) >= 32
        toks.append(x["token"])
    return rid, toks


def comment(client, tok, **kw):
    body = {"chapter": 1, "quote": "aaa", "from_offset": 0, "to_offset": 3, "body": "nice", "reaction": "none"}
    body.update(kw)
    return client.post(f"/api/read/{tok}/comments", json=body)


def test_reader_isolation(client, project):
    pid = project["id"]
    _, (a, b) = make_round(client, pid)
    assert comment(client, a, body="from A").status_code == 201
    assert comment(client, b, body="from B").status_code == 201
    va = client.get(f"/api/read/{a}").json()
    assert [c["body"] for c in va["comments"]] == ["from A"]
    assert va["book"]["title"] == "The Glass Orchard"
    assert [c["number"] for c in va["chapters"]] == [1, 2, 3]
    assert "reader_id" not in va["comments"][0]
    assert client.get("/api/read/not-a-token").status_code == 404


def test_round_chapters_only(client, project):
    pid = project["id"]
    _, (a, _b) = make_round(client, pid, chapters=(1,))
    assert [c["number"] for c in client.get(f"/api/read/{a}").json()["chapters"]] == [1]
    assert comment(client, a, chapter=2).status_code == 400


def test_closed_round_410(client, project):
    pid = project["id"]
    rid, (a, _b) = make_round(client, pid)
    assert client.post(f"/api/projects/{pid}/beta/rounds/{rid}/close").json()["status"] == "closed"
    assert client.get(f"/api/read/{a}").status_code == 410
    assert comment(client, a).status_code == 410


def test_comment_rate_limit(client, project):
    pid = project["id"]
    _, (a, b) = make_round(client, pid)
    for _ in range(ratelimit.COMMENTS_PER_HOUR):
        assert comment(client, a).status_code == 201
    assert comment(client, a).status_code == 429
    assert comment(client, b).status_code == 201  # per token


def test_insights_math(client, project):
    pid = project["id"]
    _, (a, b) = make_round(client, pid)
    for ch, pct, sec in [(1, 100, 60), (2, 40, 30), (3, 0, 0)]:
        client.post(f"/api/read/{a}/progress", json={"chapter": ch, "percent": pct, "seconds": sec})
    client.post(f"/api/read/{b}/progress", json={"chapter": 1, "percent": 96, "seconds": 120})
    comment(client, a, from_offset=50, body="early")                     # bucket 0
    comment(client, a, from_offset=999, body="", reaction="confused", quote="huh")  # bucket 9
    comment(client, b, from_offset=None, quote="", body="", reaction="confused")    # no quote -> bucket 0
    comment(client, b, from_offset=555, body="", reaction="confused", quote="huh")  # bucket 5

    d = client.get(f"/api/projects/{pid}/beta/insights").json()
    assert d["readers"] == 2
    assert d["dropoff"] == [{"chapter": 1, "started": 2, "finished": 2},
                            {"chapter": 2, "started": 1, "finished": 0},
                            {"chapter": 3, "started": 0, "finished": 0}]
    h1 = d["heat"][0]
    assert h1["comments"][0] == 1 and sum(h1["comments"]) == 1
    assert h1["reactions"]["confused"][9] == 1 and h1["reactions"]["confused"][5] == 1
    assert h1["reactions"]["confused"][0] == 1
    assert h1["total"][0] == 2
    assert d["confused"][0] == {"chapter": 1, "quote": "huh", "count": 2}
    assert d["reading_time"][0] == {"chapter": 1, "avg_seconds": 90, "readers": 2}
    assert d["reading_time"][2]["avg_seconds"] == 0


def test_bucket_edges():
    assert ins.bucket(0, 100) == 0
    assert ins.bucket(9, 100) == 0
    assert ins.bucket(10, 100) == 1
    assert ins.bucket(100, 100) == 9
    assert ins.bucket(None, 100) == 0


def test_finished_flag(client, project):
    pid = project["id"]
    _, (a, _b) = make_round(client, pid)
    r = client.post(f"/api/read/{a}/progress", json={"chapter": 3, "percent": 100, "seconds": 5}).json()
    assert r["finished"] is True
    me = client.get(f"/api/read/{a}").json()["reader"]
    assert me["finished"] and me["furthest_chapter"] == 3


def test_filters_and_resolve(client, project):
    pid = project["id"]
    _, (a, b) = make_round(client, pid)
    comment(client, a, reaction="love")
    comment(client, b, chapter=2, reaction="bored")
    base = f"/api/projects/{pid}/beta/comments"
    assert len(client.get(base).json()) == 2
    assert [c["reader_name"] for c in client.get(base, params={"reaction": "bored"}).json()] == ["Ben"]
    assert len(client.get(base, params={"chapter": 1}).json()) == 1
    cid = client.get(base).json()[0]["id"]
    assert client.post(f"{base}/{cid}/resolve").json()["resolved"] is True


def test_to_memory_non_binding(client, project):
    pid = project["id"]
    _, (a, _b) = make_round(client, pid)
    cid = comment(client, a, body="I lost track of who Mara is", quote="").json()["id"]
    r = client.post(f"/api/projects/{pid}/beta/comments/{cid}/to-memory", json={}).json()
    assert r["kind"] == "style"
    assert r["content"] == "Beta reader Ada on ch 1: I lost track of who Mara is"
    r2 = client.post(f"/api/projects/{pid}/beta/comments/{cid}/to-memory", json={"binding": True}).json()
    assert r2["kind"] == "decision"
    with Session(engine()) as s:
        kinds = sorted(m.kind for m in s.exec(select(Memory).where(Memory.source == f"beta:{cid}")).all())
    assert kinds == ["decision", "style"]


def test_summarize_posts_to_thread(client, project, monkeypatch):
    pid = project["id"]
    _, (a, _b) = make_round(client, pid)
    comment(client, a, chapter=2, body="Slow middle", reaction="bored")
    calls = []

    def complete(session, system, user, *, agent=None, max_tokens=None):
        calls.append(user)
        return "- Readers found the middle slow.", llm.Route("fake", "fake-1"), "fake-1"

    monkeypatch.setattr(llm, "complete", complete)
    r = client.post(f"/api/projects/{pid}/beta/summarize")
    assert r.status_code == 202 and r.json()["run_id"]
    assert len(calls) == 1 and "Slow middle" in calls[0]
    with Session(engine()) as s:
        t = s.exec(select(Thread).where(Thread.project_id == pid, Thread.chapter == 2)).one()
        msgs = s.exec(select(Message).where(Message.thread_id == t.id)).all()
        assert any("Readers found the middle slow." in m.body and m.sender.startswith("agent:") for m in msgs)
