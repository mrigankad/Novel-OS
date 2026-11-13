"""Ollama (local + cloud) provider wiring and the model catalog."""

import urllib.error

import pytest

from core import model_catalog
from core.llm_client import LLMClient, ollama_local_base


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("NOVEL_OS_LLM_PROVIDER", "NOVEL_OS_MODEL", "OLLAMA_HOST", "OLLAMA_API_KEY",
              "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
              "AZURE_OPENAI_API_KEY", "NOVEL_OS_API_KEY", "NOVEL_OS_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize("host,expected", [
    (None, "http://localhost:11434"),
    ("0.0.0.0:11500", "http://0.0.0.0:11500"),
    ("http://gpu-box:11434/", "http://gpu-box:11434"),
    ("http://gpu-box:11434/v1", "http://gpu-box:11434"),
])
def test_ollama_local_base_honours_ollama_host(monkeypatch, host, expected):
    if host:
        monkeypatch.setenv("OLLAMA_HOST", host)
    assert ollama_local_base() == expected


def test_ollama_api_key_selects_ollama_cloud(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "ok-test")
    client = LLMClient()
    assert client.provider == "ollama_cloud"
    assert client.model == "gpt-oss:120b"
    assert str(client._backend.base_url).startswith("https://ollama.com/v1")


def test_local_ollama_uses_ollama_host(monkeypatch):
    monkeypatch.setenv("NOVEL_OS_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434")
    client = LLMClient()
    assert str(client._backend.base_url).startswith("http://gpu-box:11434/v1")


def test_lists_local_ollama_models():
    calls = []

    def fetch(url, headers):
        calls.append((url, headers))
        return {"models": [
            {"name": "qwen3:32b", "size": 1, "details": {"family": "qwen3", "parameter_size": "32B"}},
            {"name": "gemma3:27b", "details": {}},
        ]}

    out = model_catalog.list_models("ollama", fetch=fetch)
    assert out["ok"] is True
    assert [m["id"] for m in out["models"]] == ["gemma3:27b", "qwen3:32b"]
    assert out["models"][1]["parameters"] == "32B"
    assert calls == [("http://localhost:11434/api/tags", {})]


def test_ollama_cloud_sends_bearer_key(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "ok-secret")
    seen = {}

    def fetch(url, headers):
        seen.update(url=url, headers=headers)
        return {"models": [{"name": "gpt-oss:120b"}]}

    out = model_catalog.list_models("ollama_cloud", fetch=fetch)
    assert out["ok"] and out["models"][0]["id"] == "gpt-oss:120b"
    assert seen["url"] == "https://ollama.com/api/tags"
    assert seen["headers"] == {"Authorization": "Bearer ok-secret"}
    assert "ok-secret" not in str(out)


def test_ollama_cloud_without_key_explains_itself():
    out = model_catalog.list_models("ollama_cloud", fetch=lambda u, h: pytest.fail("no call"))
    assert out["ok"] is False and "API key" in out["error"]


def test_ollama_not_running_is_a_friendly_error():
    def fetch(url, headers):
        raise urllib.error.URLError("connection refused")

    out = model_catalog.list_models("ollama", fetch=fetch)
    assert out["ok"] is False
    assert "ollama serve" in out["error"]


def test_openai_compatible_lists_models(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")

    def fetch(url, headers):
        assert url == "https://openrouter.ai/api/v1/models"
        assert headers["Authorization"] == "Bearer or-test"
        return {"data": [{"id": "b/model"}, {"id": "a/model"}]}

    out = model_catalog.list_models("openrouter", fetch=fetch)
    assert [m["id"] for m in out["models"]] == ["a/model", "b/model"]


def test_bad_key_hint():
    def fetch(url, headers):
        raise urllib.error.HTTPError(url, 401, "nope", {}, None)

    out = model_catalog.list_models("openai", api_key="sk-bad", fetch=fetch)
    assert out["ok"] is False and "API key" in out["error"]


def test_explicit_key_and_base_url_honoured_for_native_providers(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    # No env keys are set (see _clean_env); construction must not touch the network.
    a = LLMClient(provider="anthropic", api_key="sk-ant-explicit", base_url="https://proxy.example/anthropic")
    assert a._backend.api_key == "sk-ant-explicit"
    assert str(a._backend.base_url).startswith("https://proxy.example/anthropic")
    o = LLMClient(provider="openai", api_key="sk-explicit", base_url="https://proxy.example/v1")
    assert o._backend.api_key == "sk-explicit"
    assert str(o._backend.base_url).startswith("https://proxy.example/v1")
    plain = LLMClient(provider="openai", api_key="sk-explicit")
    assert str(plain._backend.base_url).startswith("https://api.openai.com")


def test_complete_stream_openai_shape():
    client = LLMClient(provider="ollama_cloud", api_key="ok-x")

    class Delta:
        def __init__(self, c):
            self.content = c

    class Choice:
        def __init__(self, c):
            self.delta = Delta(c)

    class Ev:
        def __init__(self, c):
            self.choices = [Choice(c)]

    class Completions:
        def create(self, **kw):
            assert kw["stream"] is True
            return iter([Ev("Once "), Ev(None), Ev("upon")])

    class Chat:
        completions = Completions()

    class Backend:
        chat = Chat()

    client._backend = Backend()
    assert "".join(client.complete_stream("s", "u")) == "Once upon"
