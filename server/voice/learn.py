"""Voice learning: deterministic traits plus one LLM pass for signature moves and the style guide."""

from __future__ import annotations

import json
import re

from sqlmodel import Session, select

from .. import events, llm
from ..db import session_scope
from ..models import VoiceProfile, VoiceSample
from ..models.base import now
from .analyze import compute_traits

MAX_PROMPT_CHARS = 24_000

SYSTEM = """You are the Style Curator for a novelist. You study the author's own writing and
describe their voice so other models can write like them. Reply with JSON only:
{"signature_moves": [{"example": "<verbatim quote from the samples, at most 25 words>", "note": "<plain-language note on what the move does>"}],
 "never": ["<thing this author avoids>"],
 "style_guide": "<150-250 word directive written to a model, imperative voice, e.g. 'Write in close third... end paragraphs on short falling sentences...'>"}
Give 3 to 6 signature moves. Quotes must be copied exactly from the samples."""


def combined_text(session: Session, project_id: str) -> tuple[str, int]:
    samples = session.exec(select(VoiceSample).where(VoiceSample.project_id == project_id)).all()
    return "\n\n".join(s.text for s in samples), len(samples)


def get_or_create_profile(session: Session, project_id: str) -> VoiceProfile:
    prof = session.exec(select(VoiceProfile).where(VoiceProfile.project_id == project_id)).first()
    if not prof:
        prof = VoiceProfile(project_id=project_id)
    return prof


def _parse(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _clean_moves(moves: object, source: str) -> list[dict]:
    out = []
    for mv in moves if isinstance(moves, list) else []:
        if not isinstance(mv, dict):
            continue
        ex = " ".join(str(mv.get("example", "")).split())
        words = ex.split()
        if len(words) > 25:
            ex = " ".join(words[:25]) + "..."
        if ex:
            out.append({"example": ex, "note": str(mv.get("note", "")).strip(),
                        "verbatim": ex.rstrip(".") in " ".join(source.split())})
    return out[:6]


def _brief(traits: dict) -> str:
    keep = {k: v for k, v in traits.items() if k not in ("openers",)}
    return json.dumps(keep, ensure_ascii=False)


def learn(project_id: str, run_id: str = "inline") -> dict:
    """Recompute the VoiceProfile for a project. Runs inside a job."""
    with session_scope() as s:
        text, n = combined_text(s, project_id)
        if not text.strip():
            raise ValueError("Add at least one writing sample first.")
        traits = compute_traits(text)
        user = (f"Measured traits:\n{_brief(traits)}\n\nAuthor samples:\n\"\"\"\n"
                f"{text[:MAX_PROMPT_CHARS]}\n\"\"\"")
        reply, _route, model = llm.complete(s, SYSTEM, user, max_tokens=2000)
        data = _parse(reply)

        prof = get_or_create_profile(s, project_id)
        prof.traits = traits
        prof.signature_moves = _clean_moves(data.get("signature_moves"), text)
        never = data.get("never")
        prof.never = [str(x).strip() for x in never if str(x).strip()] if isinstance(never, list) else []
        prof.style_guide = str(data.get("style_guide", "")).strip()
        prof.words_analyzed = traits["words"]
        prof.updated_at = now()
        s.add(prof)
        s.flush()
        out = {"profile_id": prof.id, "words_analyzed": prof.words_analyzed, "samples": n, "model": model}
    events.publish(project_id, "voice.updated", {"words_analyzed": out["words_analyzed"]})
    return out
