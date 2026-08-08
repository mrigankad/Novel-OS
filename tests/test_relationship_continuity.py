"""Relationship-aware continuity checks (R4)."""

import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from continuity_engine import (  # noqa: E402
    check_hostile_pairs_co_present,
    check_relationship_integrity,
    check_relationship_since_anachronism,
    check_contradictory_relationships,
    check_dead_bonded_co_presence,
    run_all,
)
from context_pack import build_context_pack  # noqa: E402
from state_manager import (  # noqa: E402
    Character, ChapterState, RelationshipEdge, StoryState,
)


def _state(tmp_path) -> StoryState:
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    return StoryState(str(root))


def test_orphan_relationship(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="char_001", full_name="Lena", role="protagonist"))
    s.relationships["rel-001"] = RelationshipEdge(
        id="rel-001", source_id="char_001", target_id="missing", label="ally",
    )
    findings = check_relationship_integrity(s)
    assert any(f.category == "relationship_orphan" for f in findings)


def test_hostile_co_presence(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="char_001", full_name="Lena", role="protagonist"))
    s.add_character(Character(id="char_002", full_name="Mara", role="antagonist"))
    s.relationships["rel-001"] = RelationshipEdge(
        id="rel-001", source_id="char_001", target_id="char_002", label="rivals",
    )
    s.chapters[1] = ChapterState(
        number=1, title="Meet", status="drafted",
        characters_present=["Lena", "Mara"],
    )
    findings = check_hostile_pairs_co_present(s, as_of_chapter=1)
    assert any(f.category == "hostile_co_presence" for f in findings)


def test_since_chapter_anachronism(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="char_001", full_name="Lena", role="protagonist"))
    s.add_character(Character(id="char_002", full_name="Mara", role="supporting"))
    s.relationships["rel-001"] = RelationshipEdge(
        id="rel-001", source_id="char_001", target_id="char_002",
        label="allies", since_chapter=5,
    )
    s.chapters[2] = ChapterState(
        number=2, title="Early", status="drafted",
        characters_present=["Lena", "Mara"], pov_character="Lena",
    )
    findings = check_relationship_since_anachronism(s, as_of_chapter=2)
    assert any(f.category == "relationship_since_anachronism" for f in findings)


def test_contradictory_bonds(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="char_001", full_name="Lena", role="protagonist"))
    s.add_character(Character(id="char_002", full_name="Mara", role="antagonist"))
    s.relationships["r1"] = RelationshipEdge(
        id="r1", source_id="char_001", target_id="char_002", label="enemies",
    )
    s.relationships["r2"] = RelationshipEdge(
        id="r2", source_id="char_002", target_id="char_001", label="romantic",
    )
    findings = check_contradictory_relationships(s)
    assert any(f.category == "relationship_contradiction" for f in findings)


def test_dead_bonded_co_presence(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(
        id="char_001", full_name="Lena", role="protagonist", notes="alive",
    ))
    s.add_character(Character(
        id="char_002", full_name="Mara", role="supporting", notes="killed in ch1",
    ))
    s.relationships["rel-001"] = RelationshipEdge(
        id="rel-001", source_id="char_001", target_id="char_002", label="allies",
    )
    s.chapters[3] = ChapterState(
        number=3, title="Ghost", status="drafted",
        characters_present=["Lena", "Mara"], pov_character="Lena",
    )
    findings = check_dead_bonded_co_presence(s, as_of_chapter=3)
    assert any(f.category == "dead_character_co_presence" and f.severity == "critical" for f in findings)


def test_guardian_pack_neighborhood_from_prose(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="c1", full_name="Lena Marrow", role="protagonist",
                              last_appearance_chapter=1))
    s.add_character(Character(id="c2", full_name="Mara Vale", role="antagonist",
                              last_appearance_chapter=1))
    s.relationships["r1"] = RelationshipEdge(
        id="r1", source_id="c1", target_id="c2", label="rivals",
    )
    s.chapters[4] = ChapterState(number=4, title="Clash", pov_character="Lena Marrow")
    pack = build_context_pack(
        s, 4, purpose="guardian",
        chapter_text="Lena Marrow watched the pier. Rain slicked the stones.",
    )
    ids = {c["id"] for c in pack.cast}
    assert "c1" in ids
    assert "c2" in ids  # 1-hop neighborhood from POV/prose
    assert any(c.get("why") == "neighborhood" for c in pack.cast)


def test_codex_block_includes_relationships(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="char_001", full_name="Lena", role="protagonist"))
    s.add_character(Character(id="char_002", full_name="Mara", role="supporting"))
    s.add_relationship("char_001", "char_002", "allies")
    block = s.format_codex_block()
    assert "Relationships" in block
    assert "Lena" in block and "Mara" in block
    assert "allies" in block


def test_run_all_includes_relationship_checks(tmp_path):
    s = _state(tmp_path)
    s.relationships["rel-x"] = RelationshipEdge(
        id="rel-x", source_id="a", target_id="b", label="enemy",
    )
    findings = run_all(s)
    assert any(f.category == "relationship_orphan" for f in findings)


def test_run_all_honours_as_of_chapter_for_every_check_that_takes_it(tmp_path):
    """A check that accepts as_of_chapter must actually receive it.

    run_all used to pick the arity by catching TypeError, so a TypeError raised
    inside a two-arg check silently re-ran it against the default chapter and
    reported findings for the wrong point in the story.
    """
    import continuity_engine as ce

    s = _state(tmp_path)
    seen: list[object] = []

    def check_records_chapter(state, as_of_chapter=None):
        seen.append(as_of_chapter)
        return []

    original = ce.ALL_CHECKS
    ce.ALL_CHECKS = (check_records_chapter,)
    try:
        ce.run_all(s, as_of_chapter=7)
    finally:
        ce.ALL_CHECKS = original

    assert seen == [7]


def test_run_all_does_not_swallow_a_typeerror_raised_inside_a_check(tmp_path):
    import continuity_engine as ce

    s = _state(tmp_path)

    def check_explodes(state, as_of_chapter=None):
        raise TypeError("boom from inside the check")

    original = ce.ALL_CHECKS
    ce.ALL_CHECKS = (check_explodes,)
    try:
        with pytest.raises(TypeError, match="boom from inside"):
            ce.run_all(s, as_of_chapter=3)
    finally:
        ce.ALL_CHECKS = original
