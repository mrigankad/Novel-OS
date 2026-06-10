"""Shared pytest setup: put the `core` package dir on sys.path.

The core modules import each other by top-level name (e.g. `from llm_client import ...`),
so we add `core/` to the path rather than importing it as a package.
"""

import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
