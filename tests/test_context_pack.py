"""Tests for ranked chapter context packs."""

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from context_pack import (  # noqa: E402
    build_context_pack,
    format_context_pack,
    slice_chapter_for_llm,
)
from state_manager import (  # noqa: E402
    Character,
    ChapterState,
    CodexEntry,
    RelationshipEdge,
    StoryState,
)


def _state(tmp_path) -> StoryState:
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    return StoryState(str(root))


def test_pack_keeps_pov_and_linked_rival(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(
        id="c1", full_name="Lena", role="protagonist", last_appearance_chapter=10,
    ))
    s.add_character(Character(
        id="c2", full_name="Mara", role="antagonist", last_appearance_chapter=1,
    ))
    s.add_character(Character(
        id="c3", full_name="Extra", role="minor", last_appearance_chapter=1,
    ))
    s.relationships["r1"] = RelationshipEdge(
        id="r1", source_id="c1", target_id="c2", label="rivals",
    )
    s.chapters[10] = ChapterState(number=10, title="Clash", pov_character="Lena", status="planned")
    pack = build_context_pack(s, 10, purpose="guardian")
    ids = {c["id"] for c in pack.cast}
    assert "c1" in ids
    assert "c2" in ids  # via bond, despite dormant appearance
    assert any(b["label"] == "rivals" for b in pack.bonds)


def test_slice_chapter_head_tail():
    text = "A" * 6000 + "M" * 3000 + "Z" * 4000  # 13000 > soft_limit
    out = slice_chapter_for_llm(text)
    assert out.startswith("A" * 100)
    assert out.endswith("Z" * 100)
    assert "omitted" in out.lower()


def test_slice_short_chapter_unchanged():
    text = "Short chapter body."
    assert slice_chapter_for_llm(text) == text


def test_format_includes_sections_and_budget(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="c1", full_name="Lena", role="protagonist", last_appearance_chapter=2))
    s.chapters[2] = ChapterState(number=2, title="Two", pov_character="Lena")
    s.chapters[1] = ChapterState(number=1, title="One", pov_character="Lena")
    for i in range(20):
        s.codex[f"loc{i}"] = CodexEntry(
            id=f"loc{i}", entry_type="location", name=f"Place{i}",
            summary=("detail " * 40),
        )
    pack = build_context_pack(s, 2, purpose="continue")  # tight 3000 budget
    md = format_context_pack(pack)
    assert "Context pack" in md
    assert "Lena" in md
    assert pack.budgets["max_chars"] == 3000
    # Either dropped items or stayed under budget
    assert pack.budgets.get("used_chars", 0) <= 3200 or pack.dropped


def test_prior_chapter_synopsis_fallback(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="c1", full_name="Lena", role="protagonist", last_appearance_chapter=3))
    s.chapters[3] = ChapterState(number=3, title="Three", pov_character="Lena")
    s.chapters[2] = ChapterState(number=2, title="The Pier", pov_character="Lena")
    pack = build_context_pack(s, 3, purpose="architect")
    assert pack.prior_chapters
    assert pack.prior_chapters[0]["number"] == 2
    assert "Pier" in pack.prior_chapters[0]["synopsis"] or "Lena" in pack.prior_chapters[0]["synopsis"]
