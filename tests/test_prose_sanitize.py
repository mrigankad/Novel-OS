"""Prose sanitization: no em dashes, strip CHAPTER HTML headers."""

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from prose_sanitize import (  # noqa: E402
    apply_header_to_chapter,
    sanitize_manuscript,
    strip_em_dashes,
)


def test_strip_em_dashes():
    assert strip_em_dashes("Hello world") == "Hello world"
    assert "—" not in strip_em_dashes("Hello—there")
    assert strip_em_dashes("Hello—there") == "Hello - there"
    assert strip_em_dashes("Hello — there") == "Hello - there"


def test_repair_spaced_hyphen_corruption():
    from prose_sanitize import repair_spaced_hyphen_corruption
    bad = (
        "She - went - back - to - the - crate. - She - did - not - take - "
        "the - folder - some - version - of - her - still - believed."
    )
    fixed = repair_spaced_hyphen_corruption(bad)
    assert " - " not in fixed
    assert "She went back to the crate." in fixed
    # Intentional pauses stay
    ok = "She paused - then opened the drawer. Later she left."
    assert repair_spaced_hyphen_corruption(ok) == ok


def test_sanitize_removes_header_and_state_block():
    raw = """<!--
CHAPTER: 1 - The Weight of Small Hours
POV: Ilse Vardan
LOCATION: Sub-basement Records Annex
TIME: 11:00 PM
WORD COUNT: ~2550 / 2500
-->

Ilse paused then opened the drawer.

[SCRIBE_STATE_UPDATE]
Characters_Present:
  - Ilse Vardan
Key_Events:
  - Found the ledger
[/SCRIBE_STATE_UPDATE]
"""
    body, meta = sanitize_manuscript(raw)
    assert "<!--" not in body
    assert "SCRIBE_STATE" not in body
    assert "—" not in body
    assert "Ilse paused" in body
    assert meta["title"] == "The Weight of Small Hours"
    assert meta["pov"] == "Ilse Vardan"
    assert meta["location"].startswith("Sub-basement")
    assert meta["word_count"] == 2550


def test_apply_header_to_chapter():
    class Ch:
        title = ""
        pov_character = ""
        location = ""
        time = ""
        word_count = 0

    ch = Ch()
    apply_header_to_chapter(ch, {
        "title": "Blue Lanterns",
        "pov": "Lena",
        "location": "Pier",
        "time": "dusk",
        "word_count": 420,
    })
    assert ch.title == "Blue Lanterns"
    assert ch.pov_character == "Lena"
    assert ch.word_count == 420
