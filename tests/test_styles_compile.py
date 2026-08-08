"""Named styles (P5.2) and the compile engine (P6).

The split under test: gathering decides *what* is in the book, rendering decides
what it looks like. Keeping them apart is what makes DOCX and EPUB new renderers
rather than new walks of the manuscript.
"""

import sys
from pathlib import Path

import pytest

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from compile_book import (  # noqa: E402
    gather, parse_chapter, render, render_html, render_markdown,
)
from styles import (  # noqa: E402
    STYLE_ROLES, Style, StyleError, StyleSheet, default_styles, parse, validate,
)


# ------------------------------------------------------------------ styles

def test_defaults_cover_every_role():
    assert set(default_styles()) == set(STYLE_ROLES)


def test_body_indents_but_the_first_paragraph_does_not():
    """The single most visible mark of typeset text."""
    s = default_styles()
    assert s["body"].first_line_indent_em > 0
    assert s["first_paragraph"].first_line_indent_em == 0


def test_chapters_start_on_a_new_page():
    assert default_styles()["chapter_title"].page_break_before is True


def test_a_missing_role_falls_back_to_body_rather_than_failing():
    """An export must never die on the eve of a deadline."""
    sheet = StyleSheet(styles={"body": Style(size_pt=13)})
    assert sheet.get("block_quote").size_pt == 13


def test_an_empty_sheet_still_resolves_a_role():
    assert StyleSheet(styles={}).get("body").size_pt > 0


def test_round_trips_through_a_dict():
    sheet = StyleSheet(scene_break_marker="~~~")
    sheet.styles["body"] = Style(size_pt=13.5, italic=True)
    back = StyleSheet.from_dict(sheet.to_dict())
    assert back.scene_break_marker == "~~~"
    assert back.styles["body"].size_pt == 13.5
    assert back.styles["body"].italic is True


def test_a_partial_sheet_keeps_the_defaults_for_everything_else():
    sheet = StyleSheet.from_dict({"styles": {"body": {"size_pt": 14}}})
    assert sheet.styles["body"].size_pt == 14
    assert sheet.styles["chapter_title"].bold is True


def test_unknown_roles_are_ignored_on_load_and_rejected_on_parse():
    sheet = StyleSheet.from_dict({"styles": {"nonsense": {"size_pt": 14}}})
    assert "nonsense" not in sheet.styles

    sheet.styles["nonsense"] = Style()
    assert any("nonsense" in p for p in validate(sheet))


@pytest.mark.parametrize("field_name,value,word", [
    ("size_pt", 300, "size"),
    ("line_height", 9, "line height"),
    ("align", "sideways", "alignment"),
    ("font", "comic", "font"),
    ("first_line_indent_em", 50, "indent"),
])
def test_nonsense_values_are_reported_in_words_a_writer_can_act_on(
    field_name, value, word,
):
    sheet = StyleSheet()
    setattr(sheet.styles["body"], field_name, value)
    problems = validate(sheet)
    assert any(word in p for p in problems), problems


def test_parse_raises_with_every_problem_at_once():
    with pytest.raises(StyleError) as e:
        parse({"styles": {"body": {"size_pt": 300, "align": "sideways"}}})
    assert "size" in str(e.value) and "alignment" in str(e.value)


def test_parse_accepts_a_good_sheet():
    assert parse({"styles": {"body": {"size_pt": 11}}}).styles["body"].size_pt == 11


# ----------------------------------------------------------------- parsing

def kinds(blocks):
    return [b.kind for b in blocks]


def test_paragraphs_split_on_blank_lines():
    assert kinds(parse_chapter("One.\n\nTwo.")) == ["first_paragraph", "body"]


def test_a_wrapped_paragraph_becomes_one_block():
    out = parse_chapter("She went\ndown to the\nwater.")
    assert len(out) == 1
    assert out[0].text == "She went down to the water."


def test_a_heading_becomes_a_chapter_title():
    out = parse_chapter("# The Pier\n\nShe waited.")
    assert kinds(out) == ["chapter_title", "first_paragraph"]
    assert out[0].text == "The Pier"


def test_the_paragraph_after_a_scene_break_is_not_indented():
    out = parse_chapter("One.\n\n---\n\nTwo.\n\nThree.")
    assert kinds(out) == ["first_paragraph", "scene_break", "first_paragraph", "body"]


@pytest.mark.parametrize("marker", ["---", "***", "* * *", "___", "- - -"])
def test_every_common_scene_break_marker_is_recognised(marker):
    assert kinds(parse_chapter("One.\n\n" + marker + "\n\nTwo.")) == [
        "first_paragraph", "scene_break", "first_paragraph",
    ]


def test_a_quoted_passage_becomes_a_block_quote():
    out = parse_chapter("> Dear Lena,\n> I am not coming.")
    assert kinds(out) == ["block_quote"]
    assert out[0].text == "Dear Lena, I am not coming."


def test_empty_prose_produces_nothing():
    assert parse_chapter("") == []
    assert parse_chapter("   \n\n  ") == []


# --------------------------------------------------------------- gathering

def _book():
    return gather(
        title="The Pier", author="M", genre="Literary",
        chapters=[
            # The second paragraph is deliberate: it is the only one that gets
            # the `body` style, so the fixture exercises indentation at all.
            {"number": 1, "title": "Arrival",
             "text": "She waited.\n\nThe tide came in.\n\n---\n\nHe did not."},
            {"number": 2, "title": "Departure", "text": "They left."},
        ],
    )


def test_gather_titles_each_chapter():
    book = _book()
    assert [c["title"] for c in book.chapters] == ["Arrival", "Departure"]
    assert book.blocks[0].kind == "chapter_title"


def test_a_chapter_that_names_itself_is_not_titled_twice():
    book = gather(title="T", author="", genre="", chapters=[
        {"number": 1, "title": "Arrival", "text": "# Arrival\n\nShe waited."},
    ])
    assert kinds(book.blocks).count("chapter_title") == 1
    assert book.chapters[0]["title"] == "Arrival"


def test_an_untitled_chapter_gets_a_number():
    book = gather(title="T", author="", genre="", chapters=[
        {"number": 4, "title": "", "text": "She waited."},
    ])
    assert book.chapters[0]["title"] == "Chapter 4"


def test_empty_chapters_are_skipped_entirely():
    book = gather(title="T", author="", genre="", chapters=[
        {"number": 1, "title": "One", "text": ""},
        {"number": 2, "title": "Two", "text": "Words."},
    ])
    assert [c["number"] for c in book.chapters] == [2]


def test_word_count_ignores_titles_and_ornaments():
    book = gather(title="T", author="", genre="", chapters=[
        {"number": 1, "title": "A Very Long Chapter Title", "text": "one two three"},
    ])
    assert book.word_count == 3


def test_blocks_carry_their_chapter_for_navigation():
    assert {b.chapter for b in _book().blocks} == {1, 2}


# --------------------------------------------------------------- rendering

def test_html_is_self_contained_and_uses_the_stylesheet():
    out = render_html(_book(), StyleSheet())
    assert out.startswith("<!doctype html>")
    assert "<title>The Pier</title>" in out
    # No external stylesheet: an emailed export must stand alone.
    assert "<link" not in out
    assert "text-indent" in out


def test_the_scene_break_marker_is_honoured():
    sheet = StyleSheet(scene_break_marker="~ ~ ~")
    assert "~ ~ ~" in render_html(_book(), sheet)


def test_style_changes_reach_the_output():
    sheet = StyleSheet()
    sheet.styles["body"] = Style(size_pt=99, align="center")
    assert "font-size:99pt" in render_html(_book(), sheet)


def test_html_escapes_prose_rather_than_trusting_it():
    book = gather(title="T & Co", author="", genre="", chapters=[
        {"number": 1, "title": "One", "text": "<script>alert(1)</script>"},
    ])
    out = render_html(book, StyleSheet())
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "T &amp; Co" in out


def test_inline_emphasis_survives_into_html():
    book = gather(title="T", author="", genre="", chapters=[
        {"number": 1, "title": "One", "text": "She was **certain** and *calm*."},
    ])
    out = render_html(book, StyleSheet())
    assert "<strong>certain</strong>" in out
    assert "<em>calm</em>" in out


def test_markdown_render_has_no_styling():
    md = render_markdown(_book(), StyleSheet())
    assert md.startswith("# The Pier")
    assert "font-size" not in md
    assert "## Arrival" in md


def test_render_dispatches_by_format():
    assert render(_book(), StyleSheet(), "html").startswith("<!doctype")
    assert render(_book(), StyleSheet(), "markdown").startswith("# ")


def test_an_unknown_format_says_what_is_available():
    with pytest.raises(ValueError) as e:
        render(_book(), StyleSheet(), "docx")
    assert "html" in str(e.value) and "markdown" in str(e.value)
