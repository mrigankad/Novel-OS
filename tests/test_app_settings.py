from app_settings import (
    merge_system_prompt,
    read_global_system_prefix,
    read_max_concurrent_llm,
    write_global_system_prefix,
    write_max_concurrent_llm,
)


def test_merge_system_prefix_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert merge_system_prompt("Agent body") == "Agent body"


def test_merge_system_prefix_prepends(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_global_system_prefix("Always past tense.")
    merged = merge_system_prompt("You are the Scribe.")
    assert merged.startswith("Always past tense.")
    assert "You are the Scribe." in merged
    assert "---" in merged


def test_read_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_global_system_prefix("  hello  ")
    assert read_global_system_prefix().strip() == "hello"


def test_max_concurrent_llm_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert read_max_concurrent_llm() == 2
    assert write_max_concurrent_llm(4) == 4
    assert read_max_concurrent_llm() == 4
    monkeypatch.setenv("NOVEL_OS_MAX_CONCURRENT_LLM", "6")
    assert read_max_concurrent_llm() == 6
