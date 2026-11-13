"""Continuity checks over the database. Owner: manuscript area.

Other areas call continuity_findings(); the Guardian agent and the MCP server use it.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session


def continuity_findings(session: Session, project_id: str, chapter: Optional[int] = None) -> list[dict]:
    """Deterministic findings: [{"key", "severity": critical|warning|info, "kind", "message",
    "chapter", "entity"}], with author exemptions already removed."""
    return []
