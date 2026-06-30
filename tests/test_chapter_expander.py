"""Tests for [[expand: …]] placeholder detection and expansion helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_expander import PLACEHOLDER_RE, find_placeholders, extract_expanded_chapter  # noqa: E402


def test_find_placeholders():
    text = (
        "She walked in.\n\n"
        "[[expand: describe the smoke-filled tavern in sensory detail]]\n\n"
        "He waited by the door."
    )
    found = find_placeholders(text)
    assert len(found) == 1
    assert "smoke-filled tavern" in found[0].instruction
    assert found[0].raw.startswith("[[expand:")


def test_find_ai_alias():
    text = "Before [[ai: a tense dialogue about the letter]] after."
    assert len(find_placeholders(text)) == 1


def test_extract_expanded_chapter_block():
    raw = """Note: expanded two scenes.

[EXPANDED_CHAPTER]
She walked in. The tavern stank of ale and ash.

He waited by the door.
[/EXPANDED_CHAPTER]
"""
    assert "tavern stank" in extract_expanded_chapter(raw)


def test_placeholder_regex_multiline():
    text = "[[expand:\n  multi-line\n  instruction\n]]"
    assert PLACEHOLDER_RE.search(text) is not None
