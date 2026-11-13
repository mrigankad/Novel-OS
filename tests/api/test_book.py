from sqlmodel import Session, select


def _sample(client):
    r = client.post("/api/projects/sample")
    assert r.status_code == 201
    return r.json()


def test_chapters_crud_and_word_counts(client, project):
    pid = project["id"]
    base = f"/api/projects/{pid}/chapters"
    a = client.post(base, json={"title": "One"}).json()
    b = client.post(base, json={"title": "Two", "act": 2}).json()
    c = client.post(base, json={"title": "Three"}).json()
    assert [a["number"], b["number"], c["number"]] == [1, 2, 3]
    assert c["act"] == 2  # inherits the previous chapter's act

    rows = client.get(base).json()
    assert [r["title"] for r in rows] == ["One", "Two", "Three"]
    assert "text" not in rows[0]

    before = client.get(f"/api/projects/{pid}").json()["updated_at"]
    r = client.patch(f"{base}/1", json={"text": "The frost came early to the north orchard.", "pov": "Iris"})
    assert r.status_code == 200
    assert r.json()["word_count"] == 8
    assert r.json()["status"] == "drafting"
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["word_count"] == 8
    assert proj["updated_at"] >= before

    client.patch(f"{base}/2", json={"beats": ["a", "b"], "synopsis": "s", "doc": {"type": "doc"}})
    got = client.get(f"{base}/2").json()
    assert got["beats"] == ["a", "b"] and got["doc"] == {"type": "doc"}

    # reorder: Three, One, Two
    r = client.post(f"{base}/reorder", json={"order": [c["id"], a["id"], b["id"]]})
    assert [x["title"] for x in r.json()] == ["Three", "One", "Two"]

    assert client.delete(f"{base}/1").status_code == 204
    assert [(x["number"], x["title"]) for x in client.get(base).json()] == [(1, "One"), (2, "Two")]
    assert client.get(f"{base}/3").status_code == 404


def test_versions_snapshot_restore_and_auto(client, project):
    pid = project["id"]
    base = f"/api/projects/{pid}/chapters"
    client.post(base, json={"title": "One"})
    client.patch(f"{base}/1", json={"text": "first draft words here"})
    v = client.post(f"{base}/1/versions", json={"note": "manual"}).json()
    assert v["word_count"] == 4 and v["kind"] == "snapshot"

    client.patch(f"{base}/1", json={"text": "completely different"})
    assert len(client.get(f"{base}/1/versions").json()) == 1  # small change: no auto-snapshot

    restored = client.post(f"/api/projects/{pid}/versions/{v['id']}/restore").json()
    assert restored["text"] == "first draft words here" and restored["word_count"] == 4
    versions = client.get(f"{base}/1/versions").json()
    assert any(x["note"] == "Before restore" and x["text"] == "completely different" for x in versions)

    big = " ".join(["word"] * 260)
    client.patch(f"{base}/1", json={"text": big})
    versions = client.get(f"{base}/1/versions").json()
    assert versions[0]["note"] == "Auto-snapshot" and versions[0]["word_count"] == 260


def test_codex_crud_filter_search_links_threads(client, project):
    pid = project["id"]
    base = f"/api/projects/{pid}/codex"
    iris = client.post(base, json={"kind": "character", "name": "Iris Vale", "aliases": ["Iris"],
                                   "facts": {"status": "alive"}}).json()
    orchard = client.post(base, json={"kind": "location", "name": "North Orchard"}).json()
    assert [e["name"] for e in client.get(base, params={"kind": "character"}).json()] == ["Iris Vale"]
    assert [e["id"] for e in client.get(base, params={"q": "iris"}).json()] == [iris["id"]]
    assert client.get(base, params={"q": "nobody"}).json() == []

    r = client.patch(f"{base}/{iris['id']}", json={"facts": {"status": "alive", "eyes": "grey"}})
    assert r.json()["facts"]["eyes"] == "grey"

    link = client.post(f"/api/projects/{pid}/codex-links",
                       json={"source_id": iris["id"], "target_id": orchard["id"], "label": "owns"}).json()
    assert client.get(f"/api/projects/{pid}/codex-links", params={"entry": orchard["id"]}).json()[0]["id"] == link["id"]

    t = client.post(f"/api/projects/{pid}/threads", json={"name": "Sell or keep"}).json()
    assert client.patch(f"/api/projects/{pid}/threads/{t['id']}", json={"status": "resolved"}).json()["status"] == "resolved"
    assert client.delete(f"/api/projects/{pid}/threads/{t['id']}").status_code == 204

    assert client.delete(f"{base}/{orchard['id']}").status_code == 204
    assert client.get(f"/api/projects/{pid}/codex-links").json() == []
    assert client.get(f"{base}/{orchard['id']}").status_code == 404


def test_sample_book(client):
    p = _sample(client)
    assert p["title"] == "The Glass Orchard" and p["chapter_count"] == 6
    chapters = client.get(f"/api/projects/{p['id']}/chapters").json()
    assert {c["act"] for c in chapters} == {1, 2}
    written = [c for c in chapters if c["word_count"] > 0]
    assert len(written) == 3
    assert all(300 <= c["word_count"] <= 600 for c in written)
    assert all(c["synopsis"] and c["beats"] for c in chapters if c["word_count"] == 0)
    codex = client.get(f"/api/projects/{p['id']}/codex").json()
    names = {e["name"] for e in codex}
    assert {"Iris Vale", "Tomas Reed", "Grafting knife", "North Orchard"} <= names
    assert len(client.get(f"/api/projects/{p['id']}/threads").json()) == 2


def test_continuity_finds_the_knife(client):
    p = _sample(client)
    data = client.get(f"/api/projects/{p['id']}/continuity").json()
    knife = [f for f in data["findings"] if "Grafting knife" in f["message"]]
    assert len(knife) == 1
    f = knife[0]
    assert f["severity"] == "critical" and f["chapter"] == 3 and f["kind"] == "fact_contradiction"
    # stable key, also returned when scoped to the chapter
    scoped = client.get(f"/api/projects/{p['id']}/continuity", params={"chapter": 3}).json()["findings"]
    assert f["key"] in {x["key"] for x in scoped}
    assert f["key"] not in {x["key"] for x in
                            client.get(f"/api/projects/{p['id']}/continuity", params={"chapter": 2}).json()["findings"]}


def test_continuity_dead_character_and_status_drift(client, project):
    pid = project["id"]
    client.post(f"/api/projects/{pid}/codex", json={"kind": "character", "name": "Old Harlan",
                                                    "facts": {"status": "dead", "died_chapter": 1}})
    base = f"/api/projects/{pid}/chapters"
    client.post(base, json={"title": "One", "text": "Harlan died in the frost."})
    client.post(base, json={"title": "Two", "text": "Old Harlan walked the rows at dawn."})
    client.post(base, json={"title": "Three", "status": "final"})
    kinds = {f["kind"] for f in client.get(f"/api/projects/{pid}/continuity").json()["findings"]}
    assert "dead_character_activity" in kinds
    assert "status_drift" in kinds  # created with text but status planned
    assert "missing_text" in kinds


def test_exemption_hides_finding_and_records_decision(client):
    from server.db import engine
    from server.models import Memory

    p = _sample(client)
    url = f"/api/projects/{p['id']}/continuity"
    f = next(x for x in client.get(url).json()["findings"] if "Grafting knife" in x["message"])
    r = client.post(f"{url}/exemptions", json={"key": f["key"], "message": f["message"], "reason": "A second knife"})
    assert r.status_code == 201
    assert f["key"] not in {x["key"] for x in client.get(url).json()["findings"]}
    with Session(engine()) as s:
        mem = s.exec(select(Memory).where(Memory.project_id == p["id"], Memory.kind == "decision")).all()
    assert len(mem) == 1 and mem[0].agent_id is None and "Grafting knife" in mem[0].content

    assert client.delete(f"{url}/exemptions/{f['key']}").status_code == 204
    assert f["key"] in {x["key"] for x in client.get(url).json()["findings"]}
