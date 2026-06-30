"""Tests for chapter regeneration prose extraction."""

from state_parser import extract_revised_chapter


def test_extract_revised_chapter_from_block():
    text = """Notes here.

[REVISED_CHAPTER]
The hero walked into the rain.
[/REVISED_CHAPTER]
"""
    assert extract_revised_chapter(text) == "The hero walked into the rain."


def test_extract_revised_chapter_ignores_thinking_trace():
    from chapter_regenerator import extract_chapter_prose

    text = """<think>
Format check: [BACKGROUND_STATE_UPDATE] fake [/BACKGROUND_STATE_UPDATE]
</think>

[REVISED_CHAPTER]
Real chapter prose.
[/REVISED_CHAPTER]
"""
    assert extract_chapter_prose(text) == "Real chapter prose."
