"""Tests for the setup wizard: local detection and .env persistence."""

import setup_wizard
from setup_wizard import detect_options, write_env


def test_detect_lmstudio(monkeypatch):
    monkeypatch.setattr(setup_wizard, "_port_open",
                        lambda h, p, timeout=0.4: p == 1234)
    opts = detect_options(env={})
    assert opts[0].provider == "lmstudio"
    assert opts[0].recommended is True


def test_detect_ollama(monkeypatch):
    monkeypatch.setattr(setup_wizard, "_port_open",
                        lambda h, p, timeout=0.4: p == 11434)
    opts = detect_options(env={})
    providers = [o.provider for o in opts]
    assert "ollama" in providers


def test_manual_option_always_present(monkeypatch):
    monkeypatch.setattr(setup_wizard, "_port_open", lambda h, p, timeout=0.4: False)
    opts = detect_options(env={})
    assert opts[-1].provider == "__manual__"


def test_write_env_creates_file(tmp_path):
    env = tmp_path / ".env"
    write_env({"NOVEL_OS_LLM_PROVIDER": "lmstudio"}, env)
    content = env.read_text(encoding="utf-8")
    assert "NOVEL_OS_LLM_PROVIDER=lmstudio" in content


def test_write_env_merges_and_preserves(tmp_path):
    env = tmp_path / ".env"
    env.write_text("EXISTING=keep\nNOVEL_OS_MODEL=old\n", encoding="utf-8")
    write_env({"NOVEL_OS_LLM_PROVIDER": "lmstudio"}, env)
    content = env.read_text(encoding="utf-8")
    assert "EXISTING=keep" in content
    assert "NOVEL_OS_MODEL=old" in content
    assert "NOVEL_OS_LLM_PROVIDER=lmstudio" in content


def test_write_env_no_clobber_without_confirm(tmp_path):
    env = tmp_path / ".env"
    env.write_text("NOVEL_OS_LLM_PROVIDER=ollama\n", encoding="utf-8")
    write_env({"NOVEL_OS_LLM_PROVIDER": "lmstudio"}, env, confirm=lambda msg: False)
    content = env.read_text(encoding="utf-8")
    assert "NOVEL_OS_LLM_PROVIDER=ollama" in content


def test_write_env_overwrites_with_confirm(tmp_path):
    env = tmp_path / ".env"
    env.write_text("NOVEL_OS_LLM_PROVIDER=ollama\n", encoding="utf-8")
    write_env({"NOVEL_OS_LLM_PROVIDER": "lmstudio"}, env, confirm=lambda msg: True)
    content = env.read_text(encoding="utf-8")
    assert "NOVEL_OS_LLM_PROVIDER=lmstudio" in content
