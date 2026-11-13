"""Voice DNA access. Owner: voice area. Other areas only call get_style_guide()."""

from __future__ import annotations

from sqlmodel import Session, select

from ..models import VoiceProfile

LIFT_NOTES = {
    "pure_me": "Lift: pure me. Match the author exactly; do not add techniques they don't use.",
    "me_plus_lift": ("Lift: me + lift. Keep the voice; you may borrow craft techniques for tension "
                     "and openings, never copy another writer."),
    "experiment": "Lift: experiment. Push stylistic range while keeping POV/tense fixed.",
}


def get_style_guide(session: Session, project_id: str) -> str:
    """Compact prose style guide for the author's voice ('' if not learned yet).

    Injected into Scribe / Editor / Curator prompts by the agent runtime.
    """
    prof = session.exec(select(VoiceProfile).where(VoiceProfile.project_id == project_id)).first()
    if not prof or not (prof.style_guide or prof.never):
        return ""
    parts = []
    if prof.style_guide:
        parts.append(prof.style_guide.strip())
    if prof.never:
        parts.append("Never: " + "; ".join(prof.never) + ".")
    parts.append(LIFT_NOTES.get(prof.lift, LIFT_NOTES["me_plus_lift"]))
    return "\n\n".join(parts)
