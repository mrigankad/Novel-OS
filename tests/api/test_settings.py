"""Connections, per-role routing, playground streaming and the MCP server."""

import json

import pytest
from sqlmodel import Session

SECRET = "sk-test-SECRETVALUE-9f2a"


@pytest.fixture(autouse=True)
def _no_env_detect(monkeypatch):
    for k in ("OLLAMA_API_KEY", "NOVEL_OS_LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    from server.routers import settings as st
    monkeypatch.setattr(st, "_probe_local_ollama", lambda base: False)
    monkeypatch.setattr(st, "_has_claude_cli", lambda: False)


def test_connections_crud_never_leaks_keys(client):
    r = client.post("/api/settings/connections",
                    json={"provider": "openai", "api_key": SECRET, "default_model": "gpt-4o"})
    assert r.status_code == 201
    c = r.json()
    assert SECRET not in r.text
    assert c["has_key"] is True and c["key_last4"] == "9f2a" and c["is_default"] is True
    # empty key keeps the existing one
    r = client.patch(f"/api/settings/connections/{c['id']}", json={"api_key": "", "label": "Work"})
    assert r.json()["has_key"] is True and r.json()["label"] == "Work"
    second = client.post("/api/settings/connections", json={"provider": "groq", "api_key": "gsk-abcdefgh"}).json()
    assert second["is_default"] is False
    listing = client.get("/api/settings/connections")
    assert SECRET not in listing.text and "gsk-abcdefgh" not in listing.text
    assert len(listing.json()["connections"]) == 2
    client.post(f"/api/settings/connections/{second['id']}/default")
    rows = {x["provider"]: x for x in client.get("/api/settings/connections").json()["connections"]}
    assert rows["groq"]["is_default"] and not rows["openai"]["is_default"]
    assert client.delete(f"/api/settings/connections/{second['id']}").status_code == 204
    rows = client.get("/api/settings/connections").json()["connections"]
    assert [x["provider"] for x in rows] == ["openai"] and rows[0]["is_default"]


def test_providers_catalogue(client):
    ids = {p["id"] for p in client.get("/api/settings/providers").json()}
    assert {"ollama", "ollama_cloud", "claude_cli", "anthropic", "openai", "gemini", "openrouter",
            "groq", "deepseek", "mistral", "lmstudio", "openai_compatible"} <= ids


def test_env_autodetects_ollama_cloud_as_default(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "ok-cloud-key-1234")
    body = client.get("/api/settings/connections")
    rows = body.json()["connections"]
    assert len(rows) == 1 and rows[0]["provider"] == "ollama_cloud" and rows[0]["is_default"]
    assert "ok-cloud-key-1234" not in body.text
    assert len(client.get("/api/settings/connections").json()["connections"]) == 1  # idempotent


def test_detection_offers_local_ollama_and_claude(client, monkeypatch):
    from server.routers import settings as st
    monkeypatch.setattr(st, "_probe_local_ollama", lambda base: True)
    monkeypatch.setattr(st, "_has_claude_cli", lambda: True)
    offers = {o["provider"] for o in client.get("/api/settings/connections").json()["detected"]}
    assert offers == {"ollama", "claude_cli"}


def test_resolve_order(client, project):
    from server import db, llm
    from server.models import Agent, Connection
    from server.models.settings_extra import RoleDefault
    with Session(db.engine()) as s:
        assert llm.resolve(s, None) is None  # nothing configured -> env auto-detect
        s.add(Connection(provider="ollama_cloud", api_key="k", default_model="gpt-oss:120b", is_default=True))
        s.add(Connection(provider="anthropic", api_key="a", default_model="claude-sonnet-4-6"))
        s.commit()
        scribe = Agent(project_id=project["id"], role="scribe", name="Scribe")
        r = llm.resolve(s, scribe)
        assert (r.provider, r.model, r.source) == ("ollama_cloud", "gpt-oss:120b", "default")
        s.add(RoleDefault(role="scribe", provider="anthropic", model="claude-opus-4-1", temperature=0.9))
        s.commit()
        r = llm.resolve(s, scribe)
        assert (r.provider, r.model, r.source, r.api_key) == ("anthropic", "claude-opus-4-1", "role", "a")
        scribe.provider, scribe.model = "ollama_cloud", "qwen3-coder:480b"
        r = llm.resolve(s, scribe)
        assert (r.provider, r.model, r.source) == ("ollama_cloud", "qwen3-coder:480b", "agent")
        assert "k" not in repr(r).replace("ollama_cloud", "")


def test_roles_get_put(client):
    roles = client.get("/api/settings/roles").json()
    assert [r["role"] for r in roles] == ["architect", "scribe", "editor", "guardian", "curator", "researcher"]
    out = client.put("/api/settings/roles", json=[{"role": "editor", "provider": "groq", "model": "m",
                                                    "temperature": 0.3}]).json()
    ed = next(r for r in out if r["role"] == "editor")
    assert ed == {"role": "editor", "provider": "groq", "model": "m", "temperature": 0.3}
    assert client.put("/api/settings/roles", json=[{"role": "nope"}]).status_code == 422


def test_models_listing_uses_connection_credentials(client, monkeypatch):
    from core import model_catalog
    seen = {}

    def fake_fetch(url, headers):
        seen.update(url=url, headers=headers)
        return {"models": [{"name": "gpt-oss:120b"}, {"name": "deepseek-v3.1:671b"}]}

    real = model_catalog.list_models
    monkeypatch.setattr(model_catalog, "list_models",
                        lambda provider, **kw: real(provider, fetch=fake_fetch, **kw))
    c = client.post("/api/settings/connections", json={"provider": "ollama_cloud", "api_key": "ok-conn-key"}).json()
    res = client.get(f"/api/settings/connections/{c['id']}/models")
    body = res.json()
    assert body["ok"] and [m["id"] for m in body["models"]] == ["deepseek-v3.1:671b", "gpt-oss:120b"]
    assert seen["headers"] == {"Authorization": "Bearer ok-conn-key"}
    assert "ok-conn-key" not in res.text


def test_test_endpoint_and_friendly_error(client, monkeypatch):
    from server import llm

    class Fake:
        model = "gpt-oss:120b"

        def complete(self, system, user):
            return "Hello, novelist, the page is waiting for you today."

    monkeypatch.setattr(llm, "client_for", lambda route, max_tokens=None: Fake())
    c = client.post("/api/settings/connections", json={"provider": "ollama_cloud", "api_key": "x" * 10}).json()
    out = client.post(f"/api/settings/connections/{c['id']}/test").json()
    assert out["ok"] and out["sample"].startswith("Hello") and "latency_ms" in out

    class Broken(Fake):
        def complete(self, system, user):
            raise RuntimeError("Error code: 401 - unauthorized")

    monkeypatch.setattr(llm, "client_for", lambda route, max_tokens=None: Broken())
    out = client.post(f"/api/settings/connections/{c['id']}/test").json()
    assert out["ok"] is False and "key" in out["error"]


def test_playground_streams_sse(client, monkeypatch):
    from server import llm
    monkeypatch.setattr(llm, "stream", lambda route, system, user, max_tokens=None: iter(["Rain ", "fell."]))
    res = client.post("/api/settings/playground", json={"role": "scribe"})
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert "".join(e.get("text", "") for e in events) == "Rain fell."
    assert events[-1]["done"] is True


# --------------------------------------------------------------- MCP round trip

async def _mcp_round_trip(project_id):
    from mcp.shared.memory import create_connected_server_and_client_session
    from server.mcp_server import build_server

    server = build_server()
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        init_tools = {t.name for t in (await session.list_tools()).tools}
        assert {"list_projects", "get_book", "get_chapter", "write_chapter", "search_codex", "add_codex_entry",
                "recall_memory", "remember", "run_continuity"} <= init_tools
        listed = await session.call_tool("list_projects", {})
        projects = json.loads(listed.content[0].text)
        assert projects["id"] == project_id if isinstance(projects, dict) else projects[0]["id"] == project_id
        w = await session.call_tool("write_chapter", {"project_id": project_id, "number": 1,
                                                      "text": "The orchard was glass at dawn."})
        assert json.loads(w.content[0].text)["word_count"] == 6
        await session.call_tool("remember", {"project_id": project_id, "content": "Mara fears the orchard."})
        rec = await session.call_tool("recall_memory", {"project_id": project_id, "query": "orchard"})
        assert "Mara" in rec.content[0].text
        cont = await session.call_tool("run_continuity", {"project_id": project_id})
        assert "count" in json.loads(cont.content[0].text)
        ch = await session.call_tool("get_chapter", {"project_id": project_id, "number": 1})
        assert "glass at dawn" in json.loads(ch.content[0].text)["text"]


def test_mcp_round_trip(client, project):
    import anyio
    anyio.run(_mcp_round_trip, project["id"])
    from server import db
    from server.models import ChapterVersion, Memory
    from sqlmodel import select
    with Session(db.engine()) as s:
        v = s.exec(select(ChapterVersion)).one()
        assert v.kind == "draft" and v.produced_by == "mcp"
        assert s.exec(select(Memory)).one().source == "mcp"
