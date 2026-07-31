"""Document tree / binder (PLAN.md P0.4).

The flat-to-tree migration is the riskiest change in the roadmap, so it is
pinned by a golden file: any change to the migrated shape has to be an explicit,
reviewed edit to `tests/golden/binder_migration.json`.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from document_tree import (  # noqa: E402
    CHAPTER, MANUSCRIPT_ID, PART, SCENE, Binder, BinderError, DocumentNode,
    build_from_chapters, migrate_status,
)
from state_manager import ChapterState, StoryState  # noqa: E402

GOLDEN = Path(__file__).parent / "golden" / "binder_migration.json"


# --------------------------------------------------------------- tree mechanics

def _binder_with_part() -> tuple[Binder, DocumentNode]:
    b = Binder()
    part = b.add(DocumentNode(type=PART, title="Manuscript"))
    return b, part


def test_children_come_back_in_insertion_order():
    b, part = _binder_with_part()
    for title in ("One", "Two", "Three"):
        b.add(DocumentNode(type=CHAPTER, title=title), part.id)
    assert [n.title for n in b.children(part.id)] == ["One", "Two", "Three"]


def test_insert_at_index_shifts_siblings():
    b, part = _binder_with_part()
    for title in ("One", "Three"):
        b.add(DocumentNode(type=CHAPTER, title=title), part.id)
    b.add(DocumentNode(type=CHAPTER, title="Two"), part.id, index=1)
    kids = b.children(part.id)
    assert [n.title for n in kids] == ["One", "Two", "Three"]
    assert [n.order for n in kids] == [0, 1, 2]


def test_walk_yields_document_order():
    b, part = _binder_with_part()
    ch = b.add(DocumentNode(type=CHAPTER, title="Ch1"), part.id)
    b.add(DocumentNode(type=SCENE, title="S1"), ch.id)
    b.add(DocumentNode(type=SCENE, title="S2"), ch.id)
    b.add(DocumentNode(type=CHAPTER, title="Ch2"), part.id)
    assert [n.title for n in b.walk()] == ["Manuscript", "Ch1", "S1", "S2", "Ch2"]


def test_move_reparents_and_renumbers_both_sides():
    b, part = _binder_with_part()
    a = b.add(DocumentNode(type=CHAPTER, title="A"), part.id)
    c = b.add(DocumentNode(type=CHAPTER, title="B"), part.id)
    scene = b.add(DocumentNode(type=SCENE, title="S"), a.id)

    b.move(scene.id, c.id)
    assert b.children(a.id) == []
    assert [n.title for n in b.children(c.id)] == ["S"]
    assert [n.order for n in b.children(part.id)] == [0, 1]


def test_move_into_own_subtree_is_refused():
    """Would orphan the subtree and strand the nodes."""
    b, part = _binder_with_part()
    ch = b.add(DocumentNode(type=CHAPTER, title="Ch"), part.id)
    scene = b.add(DocumentNode(type=SCENE, title="S"), ch.id)
    with pytest.raises(BinderError):
        b.move(ch.id, scene.id)
    with pytest.raises(BinderError):
        b.move(ch.id, ch.id)


def test_remove_takes_the_whole_subtree():
    b, part = _binder_with_part()
    ch = b.add(DocumentNode(type=CHAPTER, title="Ch"), part.id)
    b.add(DocumentNode(type=SCENE, title="S1"), ch.id)
    b.add(DocumentNode(type=SCENE, title="S2"), ch.id)

    removed = b.remove(ch.id)
    assert {n.title for n in removed} == {"Ch", "S1", "S2"}
    assert len(b) == 1  # just the part


def test_update_refuses_structural_fields():
    b, part = _binder_with_part()
    b.update(part.id, synopsis="The whole book", keywords=["a"])
    assert b.get(part.id).synopsis == "The whole book"
    with pytest.raises(BinderError):
        b.update(part.id, parent_id="somewhere-else")


def test_add_rejects_unknown_type_and_missing_parent():
    b, _ = _binder_with_part()
    with pytest.raises(BinderError):
        b.add(DocumentNode(type="chapterish", title="?"))
    with pytest.raises(BinderError):
        b.add(DocumentNode(type=SCENE, title="?"), "no-such-parent")


def test_round_trips_through_json():
    b, part = _binder_with_part()
    ch = b.add(DocumentNode(type=CHAPTER, title="Ch", chapter_number=1), part.id)
    b.add(DocumentNode(type=SCENE, title="S", synopsis="Lena runs"), ch.id)

    restored = Binder.from_list(json.loads(json.dumps(b.to_list())))
    assert [n.title for n in restored.walk()] == [n.title for n in b.walk()]
    assert restored.chapter_node(1).title == "Ch"


def test_from_dict_ignores_unknown_keys():
    """An older client must not be able to crash on a newer state file."""
    node = DocumentNode.from_dict({"id": "x", "type": SCENE, "title": "S", "future": 1})
    assert node.id == "x" and node.title == "S"


# ------------------------------------------------------------------ migration

def _chapters() -> dict:
    return {
        1: ChapterState(number=1, title="Signal", status="complete",
                        pov_character="Lena", word_count=2410,
                        target_word_count=2500,
                        scenes=[{"title": "Cold open", "summary": "The array wakes."},
                                {"summary": "Lena reads the trace."}]),
        2: ChapterState(number=2, title="", status="drafted",
                        pov_character="Malk", word_count=0),
    }


def test_migration_builds_manuscript_part_with_chapters_and_scenes():
    b = build_from_chapters(_chapters())
    assert [n.title for n in b.roots()] == ["Manuscript"]
    chapters = b.children(MANUSCRIPT_ID)
    assert [n.title for n in chapters] == ["Signal", "Chapter 2"]
    assert [n.chapter_number for n in chapters] == [1, 2]


def test_migration_gives_every_chapter_at_least_one_scene():
    """A chapter with no scenes still needs a writable leaf."""
    b = build_from_chapters(_chapters())
    ch2 = b.chapter_node(2)
    assert [n.title for n in b.children(ch2.id)] == ["Scene 1"]


def test_migration_carries_scene_summaries_into_synopses():
    b = build_from_chapters(_chapters())
    scenes = b.children(b.chapter_node(1).id)
    assert [s.title for s in scenes] == ["Cold open", "Scene 2"]
    assert scenes[0].synopsis == "The array wakes."
    assert scenes[1].synopsis == "Lena reads the trace."


def test_status_maps_onto_the_review_lifecycle():
    # Agent-produced work is never "final" until a human has reviewed it.
    assert migrate_status("planned") == "to_do"
    assert migrate_status("drafted") == "proposed"
    assert migrate_status("validated") == "in_review"
    assert migrate_status("complete") == "final"
    assert migrate_status("nonsense") == "to_do"


def test_migration_ids_are_deterministic():
    """Stable ids are what make the golden file meaningful."""
    first = build_from_chapters(_chapters()).to_list()
    second = build_from_chapters(_chapters()).to_list()
    assert [n["id"] for n in first] == [n["id"] for n in second]
    assert [n["id"] for n in first][:3] == [MANUSCRIPT_ID, "ch-001", "ch-001-s01"]


def test_migration_matches_golden_file():
    actual = build_from_chapters(_chapters()).to_list()
    if not GOLDEN.exists():  # pragma: no cover - first run only
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, indent=2), encoding="utf-8")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected, (
        "Migrated binder shape changed. If deliberate, update "
        f"{GOLDEN.relative_to(GOLDEN.parent.parent.parent)}."
    )


# ---------------------------------------------------- integration: StoryState

def test_legacy_project_gains_a_binder_on_load(tmp_path):
    """A project written before the binder existed must migrate transparently."""
    state_dir = tmp_path / "outputs" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Old Book"},
        "chapters": {"1": ChapterState(number=1, title="One").to_dict()},
    }), encoding="utf-8")

    state = StoryState(str(tmp_path))
    assert len(state.binder) == 3  # part + chapter + scene
    assert state.binder.chapter_node(1).title == "One"


def test_binder_persists_and_survives_reload(tmp_path):
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "Signal")
    state.save_state()

    assert "binder" in json.loads(
        (tmp_path / "outputs" / "state" / "story_state.json").read_text(encoding="utf-8")
    )
    assert StoryState(str(tmp_path)).binder.chapter_node(1).title == "Signal"


def test_saving_mirrors_new_chapters_into_the_tree(tmp_path):
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.save_state()
    state.create_chapter(2, "Two")
    state.save_state()

    assert [n.chapter_number for n in state.binder.children(MANUSCRIPT_ID)] == [1, 2]


def test_sync_leaves_user_renames_and_order_alone(tmp_path):
    """Structure and titles belong to the writer; sync only mirrors engine facts."""
    state = StoryState(str(tmp_path))
    state.create_chapter(1, "One")
    state.create_chapter(2, "Two")
    state.save_state()

    node = state.binder.chapter_node(1)
    state.binder.rename(node.id, "A Better Title")
    state.binder.move(node.id, MANUSCRIPT_ID, index=1)

    state.update_chapter(1, {"word_count": 1200, "status": "complete"})
    state.save_state()

    reloaded = StoryState(str(tmp_path))
    moved = reloaded.binder.chapter_node(1)
    assert moved.title == "A Better Title"          # rename preserved
    assert [n.chapter_number for n in reloaded.binder.children(MANUSCRIPT_ID)] == [2, 1]
    assert moved.word_count == 1200                  # engine fact mirrored
    assert moved.status == "final"


# ------------------------------------------------------------------- read API

def test_binder_endpoint_returns_nested_tree(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app

    root = tmp_path / "projects"
    proj = root / "book"
    (proj / "outputs" / "state").mkdir(parents=True)
    (proj / "outputs" / "state" / "story_state.json").write_text(json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A"},
        "chapters": {"1": ChapterState(number=1, title="One").to_dict()},
    }), encoding="utf-8")

    client = TestClient(create_app(
        projects_root=root, db_url=f"sqlite:///{(tmp_path / 'b.db').as_posix()}"))
    body = client.get("/api/projects/book/binder").json()

    assert [n["title"] for n in body] == ["Manuscript"]
    chapters = body[0]["children"]
    assert chapters[0]["title"] == "One"
    assert [s["title"] for s in chapters[0]["children"]] == ["Scene 1"]


def test_binder_endpoint_404s_on_unknown_project(tmp_path):
    from fastapi.testclient import TestClient
    from api.main import create_app

    root = tmp_path / "projects"
    root.mkdir()
    client = TestClient(create_app(
        projects_root=root, db_url=f"sqlite:///{(tmp_path / 'b.db').as_posix()}"))
    assert client.get("/api/projects/nope/binder").status_code == 404
