"""Tests for agent output parsing — especially local-model reasoning wrappers."""

from pathlib import Path

import pytest

from state_parser import (
    apply_background_to_state,
    apply_import_to_state,
    extract_block,
    parse_lorekeeper,
)
from state_manager import Character, StoryState


SAMPLE_WITH_REASONING = """\
<think>
Planning the output format:
[BACKGROUND_STATE_UPDATE]
Field: value
[/BACKGROUND_STATE_UPDATE]
</think>

Brief summary of the background block.

[BACKGROUND_STATE_UPDATE]
Block_Summary: Character notes for the family
Logline: A widow fights to keep her home
Tone: tense, domestic
New_Characters:
  - Jane Doe | protagonist | A determined widow
Plot_Threads:
  - Keeping the House | main | Mortgage pressure mounts | Jane Doe
[/BACKGROUND_STATE_UPDATE]
"""


def test_extract_block_skips_reasoning_trace():
    block = extract_block(SAMPLE_WITH_REASONING, "BACKGROUND_STATE_UPDATE")
    assert block is not None
    assert "Block_Summary" in block
    assert "Jane Doe" in block
    assert "Planning the output format" not in block


def test_parse_lorekeeper_from_reasoning_wrapped_output():
    parsed = parse_lorekeeper(SAMPLE_WITH_REASONING)
    assert parsed.get("block_summary") == "Character notes for the family"
    assert parsed.get("logline") == "A widow fights to keep her home"
    assert any("Jane Doe" in line for line in parsed.get("new_characters", []))


def test_apply_background_creates_characters(tmp_path):
    state = StoryState(str(tmp_path))
    parsed = parse_lorekeeper(SAMPLE_WITH_REASONING)
    changes = apply_background_to_state(state, parsed, source="test", label="bios")
    assert any("Jane Doe" in c for c in changes)
    assert state.get_character_by_name("Jane Doe") is not None
    assert len(state.plot_threads) >= 1


def test_apply_import_sets_title_when_empty(tmp_path):
    state = StoryState(str(tmp_path))
    state.create_chapter(1)
    changes = apply_import_to_state(
        state, 1, {"chapter_title": "The Archive"}, source="archivist",
    )
    assert state.get_chapter(1).title == "The Archive"
    assert any("chapter title" in c for c in changes)


def test_apply_import_keeps_existing_title(tmp_path):
    state = StoryState(str(tmp_path))
    ch = state.create_chapter(1, title="My Title")
    changes = apply_import_to_state(
        state, 1, {"chapter_title": "AI Suggestion"}, source="archivist",
    )
    assert ch.title == "My Title"
    assert any("kept chapter title" in c for c in changes)


def test_import_merges_fuzzy_name_and_registers_aliases(tmp_path):
    state = StoryState(str(tmp_path))
    state.add_character(Character(id="char_jordan", full_name="Jordan Lee", role="protagonist"))
    parsed = parse_lorekeeper("""\
Summary.

[BACKGROUND_STATE_UPDATE]
Block_Summary: Same person under another name
Logline: [None]
Tone: [None]
New_Characters:
  - Jordan | protagonist | Shorter form of Jordan Lee
Character_Updates:
  - Jordan Lee: aliases=Nickname; Mrs Quinn
[/BACKGROUND_STATE_UPDATE]
""")
    apply_background_to_state(state, parsed, source="test", label="ch1")
    jordan = state.get_character_by_name("Jordan Lee")
    assert jordan is not None
    assert len(state.characters) == 1
    assert state.get_character_by_name("Nickname") == jordan
    assert any(a.lower() == "mrs quinn" for a in jordan.aliases)
