"""Ollama admin endpoints, with httpx.MockTransport standing in for Ollama."""

import json

import httpx
import pytest

from server import ollama_admin


@pytest.fixture
def ollama(monkeypatch):
    calls: list[httpx.Request] = []
    routes: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        fn = routes.get((request.method, request.url.path))
        if fn is None:
            return httpx.Response(404, json={"error": "not found"})
        return fn(request)

    monkeypatch.setattr(ollama_admin, "TRANSPORT", httpx.MockTransport(handler))
    return routes, calls


def test_models_merge_loaded_state(client, ollama):
    routes, _ = ollama
    routes[("GET", "/api/version")] = lambda r: httpx.Response(200, json={"version": "0.9.0"})
    routes[("GET", "/api/tags")] = lambda r: httpx.Response(200, json={"models": [
        {"name": "gemma3:27b", "size": 17_000_000_000, "modified_at": "2026-01-01T00:00:00Z",
         "details": {"family": "gemma3", "parameter_size": "27.4B", "quantization_level": "Q4_K_M"}},
        {"name": "qwen3:14b", "size": 9_300_000_000, "details": {}},
    ]})
    routes[("GET", "/api/ps")] = lambda r: httpx.Response(200, json={"models": [{"name": "gemma3:27b"}]})
    body = client.get("/api/settings/ollama/models").json()
    assert body["reachable"] and body["version"] == "0.9.0"
    gemma, qwen = body["models"]
    assert gemma["loaded"] and not qwen["loaded"]
    assert gemma["parameter_size"] == "27.4B" and gemma["quantization"] == "Q4_K_M"
    assert gemma["size_human"] == "17.0 GB"
    assert body["running"][0]["name"] == "gemma3:27b"


def test_unreachable_is_friendly(client, monkeypatch):
    def boom(request):
        raise httpx.ConnectError("refused", request=request)
    monkeypatch.setattr(ollama_admin, "TRANSPORT", httpx.MockTransport(boom))
    body = client.get("/api/settings/ollama/models").json()
    assert body["reachable"] is False
    assert "ollama.com/download" in body["error"]


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_pull_streams_progress_then_done(client, ollama):
    routes, calls = ollama
    lines = [
        {"status": "pulling manifest"},
        {"status": "pulling abc", "digest": "abc", "total": 200, "completed": 82},
        {"status": "verifying sha256 digest"},
        {"status": "success"},
    ]
    routes[("POST", "/api/pull")] = lambda r: httpx.Response(
        200, content="\n".join(json.dumps(x) for x in lines).encode())
    res = client.post("/api/settings/ollama/pull/events", json={"model": "gemma3:27b"})
    assert res.status_code == 200
    assert "gzip" not in res.headers.get("content-encoding", "")
    evs = _events(res.text)
    assert evs[0] == ("progress", {"status": "pulling manifest", "percent": None, "completed": 0, "total": 0})
    assert evs[1][1]["percent"] == 41.0
    assert evs[-1][0] == "done"
    assert json.loads(calls[-1].content) == {"model": "gemma3:27b", "stream": True}


def test_pull_error_event(client, ollama):
    routes, _ = ollama
    routes[("POST", "/api/pull")] = lambda r: httpx.Response(200, content=b'{"error":"file does not exist"}\n')
    evs = _events(client.post("/api/settings/ollama/pull/events", json={"model": "nope:1b"}).text)
    assert evs == [("error", {"error": "file does not exist"})]


@pytest.mark.parametrize("name", ["bad name", "rm;-rf", "x" * 121, "", "a/../b"])
def test_invalid_model_names_rejected(client, ollama, name):
    res = client.post("/api/settings/ollama/pull/events", json={"model": name})
    assert res.status_code in (400, 422)
    assert not ollama[1]


def test_delete_calls_through(client, ollama):
    routes, calls = ollama
    routes[("DELETE", "/api/delete")] = lambda r: httpx.Response(200)
    assert client.delete("/api/settings/ollama/models/library/qwen3:14b").status_code == 204
    assert json.loads(calls[-1].content) == {"model": "library/qwen3:14b"}


def test_delete_missing_is_502(client, ollama):
    assert client.delete("/api/settings/ollama/models/qwen3:14b").status_code == 502


def test_library_lists_local_and_cloud(client):
    body = client.get("/api/settings/ollama/library").json()
    names = {m["name"]: m for m in body["models"]}
    assert names["gpt-oss:120b-cloud"]["cloud"] and not names["gemma3:27b"]["cloud"]


def test_cloud_models_never_leak_key(client, monkeypatch):
    secret = "sk-ollama-SECRET-1234"
    client.post("/api/settings/connections", json={"provider": "ollama_cloud", "api_key": secret})
    from core import model_catalog
    seen = {}

    def fake(provider, **kw):
        seen.update(kw, provider=provider)
        return {"ok": False, "models": [{"id": "gpt-oss:120b"}], "error": f"bad key {secret}"}
    monkeypatch.setattr(model_catalog, "list_models", fake)
    res = client.get("/api/settings/ollama/cloud-models")
    assert seen == {"provider": "ollama_cloud", "api_key": secret}
    assert secret not in res.text
    assert res.json()["models"] == [{"id": "gpt-oss:120b"}]
