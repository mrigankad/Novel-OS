"""Tests for reverse outline generation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from chapter_outline_generator import ChapterOutlineGenerator, extract_chapter_outline  # noqa: E402


def test_extract_chapter_outline_from_block():
    text = """Brief note.

[CHAPTER_OUTLINE]
# Chapter 1: The Rain

## Beats
1. **Opening** — Hero walks in rain.
[/CHAPTER_OUTLINE]
"""
    out = extract_chapter_outline(text)
    assert "Chapter 1" in out
    assert "Opening" in out


def test_extract_chapter_outline_ignores_thinking_trace():
    text = """<think>
[BACKGROUND_STATE_UPDATE] fake [/BACKGROUND_STATE_UPDATE]
</think>

# Chapter 2: Beats

## Chapter Goal
Something changes.
"""
    out = extract_chapter_outline(text)
    assert out.startswith("# Chapter 2")


def test_generate_outline_from_notes_dry_run(tmp_path):
    proj = tmp_path / "novel"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(
        '{"metadata":{"title":"T"},"chapters":{"1":{"number":1,"title":"Ch1","status":"planned"}},'
        '"characters":{},"plot_threads":{},"story_bible":{"logline":"A test"}}',
        encoding="utf-8",
    )
    gen = ChapterOutlineGenerator(str(proj))
    _, path = gen.generate(
        1,
        source="notes",
        instructions="Jordan finds a hidden file in the archive. End on a cliffhanger.",
        dry_run=True,
    )
    prompt = Path(path).read_text(encoding="utf-8")
    assert "OUTLINE FROM AUTHOR NOTES" in prompt
    assert "hidden file" in prompt
