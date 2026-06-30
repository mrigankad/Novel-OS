"""Tests for character profile generation parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from character_generator import parse_character_profile, profile_to_updates  # noqa: E402


SAMPLE = """
[CHARACTER_PROFILE]
Full_Name: Morgan Ellis
Role: protagonist
Age: 34
Physical_Description: Tall, dark hair, tired eyes
Internal_Desire: To know the truth about the archive
External_Goal: Expose the archive conspiracy
Fear: Losing her career and safety
Weakness: Trusts the wrong allies
Strength: Relentless curiosity
Secret: She already found one predating record
Current_Location: Central Data Archive
Emotional_State: Anxious but determined
Arc_Stage: beginning
Notes: Data archivist; wary of authority
Aliases:
  - Morgan
  - Ms. Ellis
[/CHARACTER_PROFILE]
"""


def test_parse_character_profile():
    parsed = parse_character_profile(SAMPLE)
    assert parsed.get("full_name") == "Morgan Ellis"
    assert parsed.get("role") == "protagonist"


def test_profile_to_updates():
    parsed = parse_character_profile(SAMPLE)
    updates = profile_to_updates(parsed)
    assert updates["full_name"] == "Morgan Ellis"
    assert updates["age"] == 34
    assert updates["role"] == "protagonist"
    assert "Morgan" in updates["aliases"]
    assert "archive conspiracy" in updates["external_goal"]
