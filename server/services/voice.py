"""Voice DNA access. Owner: voice area. Other areas only call get_style_guide()."""

from __future__ import annotations

from sqlmodel import Session


def get_style_guide(session: Session, project_id: str) -> str:
    """Compact prose style guide for the author's voice ('' if not learned yet).

    Injected into Scribe / Editor / Curator prompts by the agent runtime.
    """
    return ""
