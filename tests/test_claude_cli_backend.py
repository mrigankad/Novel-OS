"""Tests for the claude_cli backend and provider precedence in llm_client."""

import json
import subprocess

import pytest

import llm_client
from llm_client import LLMClient, LLMError


# --- environment helper ------------------------------------------------------

PAID_KEYS = [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "NOVEL_OS_API_KEY",
    "NOVEL_OS_BASE_URL", "NOVEL_OS_LLM_PROVIDER", "NOVEL_OS_MODEL",
]


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every provider env var (including alias keys) for a known baseline."""
    for k in PAID_KEYS:
        monkeypatch.delenv(k, raising=False)
    for _, (_, _, key_env) in llm_client.OPENAI_COMPAT_ALIASES.items():
        monkeypatch.delenv(key_env, raising=False)
    return monkeypatch


# --- precedence / resolution -------------------------------------------------

def test_claude_cli_autopicked_when_only_cli_present(clean_env):
    clean_env.setattr(llm_client.shutil, "which", lambda name: "/usr/bin/claude")
    assert LLMClient._resolve_provider() == "claude_cli"


def test_paid_key_wins_over_cli(clean_env):
    clean_env.setattr(llm_client.shutil, "which", lambda name: "/usr/bin/claude")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert LLMClient._resolve_provider() == "anthropic"


def test_explicit_provider_env_wins(clean_env):
    clean_env.setattr(llm_client.shutil, "which", lambda name: "/usr/bin/claude")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    clean_env.setenv("NOVEL_OS_LLM_PROVIDER", "claude_cli")
    assert LLMClient._resolve_provider() == "claude_cli"


def test_no_provider_and_no_cli_raises(clean_env):
    clean_env.setattr(llm_client.shutil, "which", lambda name: None)
    with pytest.raises(LLMError):
        LLMClient._resolve_provider()


def test_build_claude_cli_missing_binary_raises(clean_env):
    clean_env.setattr(llm_client.shutil, "which", lambda name: None)
    with pytest.raises(LLMError):
        LLMClient(provider="claude_cli")


# --- completion --------------------------------------------------------------

def _make_cli_client(clean_env, model=None):
    clean_env.setattr(llm_client.shutil, "which", lambda name: "/usr/bin/claude")
    return LLMClient(provider="claude_cli", model=model)


def test_complete_claude_cli_parses_result(clean_env):
    client = _make_cli_client(clean_env)
    captured = {}

    def fake_run(cmd, input=None, capture_output=None, text=None, encoding=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"result": "Hello world"}), stderr="")

    clean_env.setattr(llm_client.subprocess, "run", fake_run)
    out = client.complete(system="be brief", user="say hi")
    assert out == "Hello world"
    # system + user are folded into the message turn (not a system flag), so the
    # agent's instruction stays imperative instead of being buried under Claude
    # Code's interactive base prompt.
    assert "--append-system-prompt" not in captured["cmd"]
    assert "be brief" in captured["input"]
    assert "say hi" in captured["input"]


def test_complete_claude_cli_includes_model_flag(clean_env):
    client = _make_cli_client(clean_env, model="claude-opus-4-8")
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"result": "ok"}), stderr="")

    clean_env.setattr(llm_client.subprocess, "run", fake_run)
    client.complete(system="s", user="u")
    assert "--model" in captured["cmd"]
    assert "claude-opus-4-8" in captured["cmd"]


def test_complete_claude_cli_nonzero_exit_raises_with_login_hint(clean_env):
    client = _make_cli_client(clean_env)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not authenticated")

    clean_env.setattr(llm_client.subprocess, "run", fake_run)
    with pytest.raises(LLMError) as exc:
        client.complete(system="s", user="u")
    assert "claude login" in str(exc.value)


def test_complete_claude_cli_bad_json_raises(clean_env):
    client = _make_cli_client(clean_env)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="not json", stderr="")

    clean_env.setattr(llm_client.subprocess, "run", fake_run)
    with pytest.raises(LLMError):
        client.complete(system="s", user="u")
