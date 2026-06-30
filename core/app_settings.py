"""Install-wide settings (not per-project)."""

from __future__ import annotations

import json
import os
from pathlib import Path

SETTING_FILENAME = "global_system_prefix.md"
CONFIG_FILENAME = "app_config.json"
DEFAULT_MAX_CONCURRENT_LLM = 2
MAX_CONCURRENT_LLM_CAP = 32


def install_root() -> Path:
    return Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))


def settings_dir() -> Path:
    d = install_root() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return settings_dir() / CONFIG_FILENAME


def read_app_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_app_config(updates: dict) -> dict:
    cfg = read_app_config()
    cfg.update(updates)
    config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def read_max_concurrent_llm() -> int:
    env = os.environ.get("NOVEL_OS_MAX_CONCURRENT_LLM")
    if env:
        try:
            return max(1, min(int(env), MAX_CONCURRENT_LLM_CAP))
        except ValueError:
            pass
    raw = read_app_config().get("max_concurrent_llm_requests", DEFAULT_MAX_CONCURRENT_LLM)
    try:
        return max(1, min(int(raw), MAX_CONCURRENT_LLM_CAP))
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONCURRENT_LLM


def write_max_concurrent_llm(value: int) -> int:
    n = max(1, min(int(value), MAX_CONCURRENT_LLM_CAP))
    write_app_config({"max_concurrent_llm_requests": n})
    return n


def global_system_prefix_path() -> Path:
    return settings_dir() / SETTING_FILENAME


def read_global_system_prefix() -> str:
    path = global_system_prefix_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_global_system_prefix(text: str) -> None:
    global_system_prefix_path().write_text(text, encoding="utf-8")


def merge_system_prompt(agent_system: str) -> str:
    """Prepend install-wide instructions before each agent's system prompt."""
    prefix = read_global_system_prefix().strip()
    base = agent_system.strip()
    if not prefix:
        return base
    if not base:
        return prefix
    return f"{prefix}\n\n---\n\n{base}"
