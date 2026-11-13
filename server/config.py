"""Runtime configuration, read once from the environment (.env supported)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:  # optional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    media_dir: Path
    cors_origins: tuple[str, ...]


@lru_cache
def settings() -> Settings:
    data_dir = Path(os.environ.get("NOVEL_OS_DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_url = os.environ.get("NOVEL_OS_DATABASE_URL") or f"sqlite:///{(data_dir / 'novel_os.db').as_posix()}"
    media = data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    origins = tuple(
        o.strip()
        for o in os.environ.get("NOVEL_OS_CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    )
    return Settings(data_dir=data_dir, database_url=db_url, media_dir=media, cors_origins=origins)
