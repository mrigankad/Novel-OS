"""Ship area: media library, cover studio, metadata, releases, compile, marketing."""

from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[2] / "core"


def ensure_core_path() -> None:
    """core/compile_* use flat imports (``from styles import ...``)."""
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))


def has_pillow() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def has_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False
