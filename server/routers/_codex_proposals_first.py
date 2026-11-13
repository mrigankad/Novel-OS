"""Mount order shim: main.py mounts routers alphabetically, and book.py's GET
/projects/{id}/codex/{entry_id} would otherwise capture GET .../codex/proposals."""

from .codex_proposals import proposals_router as router  # noqa: F401
