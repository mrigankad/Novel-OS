"""
Generate a full character profile from an author prompt via the Lorekeeper agent.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from llm_client import LLMClient, LLMError
from state_manager import Character, StoryState
from state_parser import extract_block, parse_fields, _as_list


PROFILE_FIELDS = (
    "full_name",
    "role",
    "age",
    "physical_description",
    "internal_desire",
    "external_goal",
    "fear",
    "weakness",
    "strength",
    "secret",
    "current_location",
    "emotional_state",
    "arc_stage",
    "notes",
    "aliases",
)


def parse_character_profile(text: str) -> Dict[str, Any]:
    """Parse [CHARACTER_PROFILE] block from agent output."""
    block = extract_block(text, "CHARACTER_PROFILE")
    if not block:
        return {}
    return parse_fields(block)


def profile_to_updates(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Map parsed profile fields to Character model updates."""
    updates: Dict[str, Any] = {}
    if not parsed:
        return updates

    role = str(parsed.get("role", "")).strip().lower()
    if role in ("protagonist", "antagonist", "supporting", "minor"):
        updates["role"] = role

    name = str(parsed.get("full_name", "")).strip()
    if name:
        updates["full_name"] = name

    age_raw = parsed.get("age")
    if age_raw is not None and str(age_raw).strip():
        age_s = re.sub(r"[^\d]", "", str(age_raw))
        if age_s:
            updates["age"] = int(age_s)

    for key in (
        "physical_description", "internal_desire", "external_goal", "fear",
        "weakness", "strength", "secret", "current_location", "emotional_state",
        "arc_stage", "notes",
    ):
        val = parsed.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ("none", "unknown", "n/a"):
            updates[key] = text

    aliases_raw = parsed.get("aliases")
    if aliases_raw:
        aliases = _as_list(aliases_raw) if not isinstance(aliases_raw, list) else aliases_raw
        aliases = [a.strip() for a in aliases if str(a).strip()]
        if aliases:
            updates["aliases"] = aliases

    return updates


def _character_prompt(
    *,
    project_title: str,
    genre: str,
    author_prompt: str,
    existing: Optional[Character] = None,
    hint_name: str = "",
    hint_role: str = "",
) -> str:
    existing_block = ""
    if existing:
        existing_block = f"""
## Existing character record (enrich / refine — keep id and name unless prompt says otherwise)

- **ID:** {existing.id}
- **Name:** {existing.full_name}
- **Role:** {existing.role}
- **Physical:** {existing.physical_description or "(empty)"}
- **Desire:** {existing.internal_desire or "(empty)"}
- **Goal:** {existing.external_goal or "(empty)"}
- **Fear:** {existing.fear or "(empty)"}
- **Weakness:** {existing.weakness or "(empty)"}
- **Strength:** {existing.strength or "(empty)"}
- **Secret:** {existing.secret or "(empty)"}
- **Location:** {existing.current_location or "(empty)"}
- **Emotional state:** {existing.emotional_state or "(empty)"}
- **Notes:** {existing.notes or "(empty)"}
"""
    hints = ""
    if hint_name.strip():
        hints += f"\n- Suggested name: {hint_name.strip()}"
    if hint_role.strip():
        hints += f"\n- Suggested role: {hint_role.strip()}"

    return f"""# CHARACTER PROFILE GENERATION

Invent or refine a **novel character** for the project below from the author's prompt.
Output a complete character sheet — not a story scene.

- **Project:** {project_title or "Untitled"}
- **Genre:** {genre or "unspecified"}
{hints}
{existing_block}
## Author prompt

{author_prompt.strip()}

---

1. Brief note (2–4 sentences) on how you interpreted the prompt.
2. Emit `[CHARACTER_PROFILE]` as your **final** block with these fields (all required; use `[Unknown]` only if truly unknowable):

- `Full_Name` — full name
- `Role` — one of: protagonist, antagonist, supporting, minor
- `Age` — number or short phrase
- `Physical_Description` — appearance, mannerisms
- `Internal_Desire` — what they want emotionally
- `External_Goal` — what they're trying to achieve in the plot
- `Fear` — core fear
- `Weakness` — character flaw
- `Strength` — key virtue or skill
- `Secret` — what they hide (or `[None]`)
- `Current_Location` — where they are in the story now (or `[Unknown]`)
- `Emotional_State` — current mood/stance
- `Arc_Stage` — beginning, middle, climax, or resolution
- `Notes` — backstory, voice, story function (2–5 sentences)
- `Aliases` — bulleted alternate names, or `[None]`

Use exact field names. No code fences inside the block.
"""


class CharacterGenerator:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.feedback_dir = self.project_path / "outputs" / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def preview_path(self) -> Path:
        return self.feedback_dir / "character_generate_preview.json"

    def generate(
        self,
        prompt: str,
        *,
        character_id: Optional[str] = None,
        hint_name: str = "",
        hint_role: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        log = on_progress or (lambda msg: None)
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Character prompt is required.")

        existing: Optional[Character] = None
        if character_id:
            existing = self.state.get_character(character_id)
            if existing is None:
                raise ValueError(f"Unknown character {character_id!r}")

        meta = self.state.metadata
        user_prompt = _character_prompt(
            project_title=meta.get("title", ""),
            genre=meta.get("genre", ""),
            author_prompt=prompt,
            existing=existing,
            hint_name=hint_name,
            hint_role=hint_role,
        )
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = self.feedback_dir / "character_generate_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return {}

        log("Generating character profile…")
        try:
            raw = self._get_llm().run_agent("lorekeeper", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Character generation failed: {e}") from e

        report_path = self.feedback_dir / "character_generate_report.md"
        report_path.write_text(raw, encoding="utf-8")

        parsed = parse_character_profile(raw)
        updates = profile_to_updates(parsed)
        if not updates:
            raise RuntimeError("Agent returned no [CHARACTER_PROFILE] block.")

        preview = {
            "character_id": character_id,
            "prompt": prompt,
            "hint_name": hint_name.strip(),
            "hint_role": hint_role.strip(),
            "updates": updates,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.preview_path().write_text(json.dumps(preview, indent=2), encoding="utf-8")
        log(f"Profile ready ({len(updates)} fields)")
        return preview
