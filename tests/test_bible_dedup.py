"""Tests for story bible deduplication."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from bible_dedup import (  # noqa: E402
    apply_bible_dedupe_group,
    apply_bible_group_members,
    auto_dedupe_bible,
    filter_stale_bible_groups,
    find_bible_duplicate_groups,
    prune_bible_suggestion_groups,
    section_items,
)


def test_find_and_merge_bible_duplicates():
    bible = {
        "themes": [
            "family secrets",
            "Family secrets",
            "redemption",
        ],
        "premise_beats": [
            "Hero discovers a hidden archive",
            "The hero finds a secret archive",
        ],
    }
    groups = find_bible_duplicate_groups(bible, min_score=0.85)
    assert len(groups) >= 1
    assert any(g.section == "themes" for g in groups)

    log = auto_dedupe_bible(bible, min_score=0.85)
    assert log
    assert section_items(bible, "themes") == ["family secrets", "redemption"]


def test_apply_bible_dedupe_group():
    bible = {"themes": ["a", "b", "a"]}
    log, keep_idx = apply_bible_dedupe_group(bible, section="themes", keep_index=0, merge_indices=[2])
    assert log
    assert keep_idx == 0
    assert section_items(bible, "themes") == ["a", "b"]


def test_apply_bible_group_with_text_override():
    bible = {
        "setting_summary": [
            "Four-story brick building with elevator",
            "Building has four floors and an elevator",
        ],
    }
    members = [
        {"section": "setting_summary", "index": 0, "label": bible["setting_summary"][0], "id": "setting_summary:0"},
        {"section": "setting_summary", "index": 1, "label": bible["setting_summary"][1], "id": "setting_summary:1"},
    ]
    log = apply_bible_group_members(
        bible,
        members,
        "setting_summary",
        1,
        text_override="Harbor Tower: four-story brick facade, elevator, mirrored lobby.",
    )
    assert log
    assert len(section_items(bible, "setting_summary")) == 1
    assert "Harbor Tower" in section_items(bible, "setting_summary")[0]


def test_prune_and_filter_bible_ai_groups():
    bible = {
        "setting_summary": [
            "Line A kept",
            "Line B removed",
        ],
    }
    groups = [{
        "section": "setting_summary",
        "confidence": 0.95,
        "reason": "AI",
        "suggested_keep_index": 0,
        "members": [
            {"id": "setting_summary:0", "section": "setting_summary", "index": 0, "label": "Line A kept"},
            {"id": "setting_summary:1", "section": "setting_summary", "index": 1, "label": "Line B removed"},
        ],
    }]
    pruned = prune_bible_suggestion_groups(groups, {"setting_summary:0", "setting_summary:1"})
    assert pruned == []
    bible["setting_summary"] = ["Line A kept"]
    filtered = filter_stale_bible_groups(bible, groups)
    assert filtered == []
