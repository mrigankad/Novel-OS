"""ProseMirror ↔ markdown conversion (PLAN.md P1).

The markdown projection is what the five agents read, so a conversion bug here
would silently corrupt what the pipeline sees. Round-trip fixtures are the
main defence.
"""

import pytest

from api import richtext as rt


def md(doc):
    return rt.to_markdown(doc)


def doc(*blocks):
    return {"type": rt.DOC, "content": list(blocks)}


def para(*content):
    return {"type": rt.PARAGRAPH, "content": list(content)}


def text(t, *marks):
    node = {"type": rt.TEXT, "text": t}
    if marks:
        node["marks"] = [{"type": m} if isinstance(m, str) else m for m in marks]
    return node


# ---------------------------------------------------------------- doc -> md

def test_paragraphs_are_blank_line_separated():
    out = md(doc(para(text("One.")), para(text("Two."))))
    assert out == "One.\n\nTwo.\n"


def test_marks_become_delimiters():
    assert md(doc(para(text("bold", "bold")))) == "**bold**\n"
    assert md(doc(para(text("soft", "italic")))) == "*soft*\n"
    assert md(doc(para(text("gone", "strike")))) == "~~gone~~\n"
    assert md(doc(para(text("x", "code")))) == "`x`\n"


def test_links_wrap_their_marked_text():
    node = text("Novel OS", {"type": "link", "attrs": {"href": "https://x.dev"}})
    assert md(doc(para(node))) == "[Novel OS](https://x.dev)\n"


def test_headings_use_hashes():
    assert md(doc({"type": rt.HEADING, "attrs": {"level": 2},
                   "content": [text("Chapter One")]})) == "## Chapter One\n"


def test_horizontal_rule_is_the_scene_break():
    assert md(doc({"type": rt.HORIZONTAL_RULE})) == "---\n"


def test_images_serialise_with_alt_and_title():
    node = {"type": rt.IMAGE,
            "attrs": {"src": "/api/x/raw", "alt": "Lena", "title": "At the array"}}
    assert md(doc(node)) == '![Lena](/api/x/raw "At the array")\n'


def test_blockquote_prefixes_every_line():
    out = md(doc({"type": rt.BLOCKQUOTE, "content": [para(text("Quoted."))]}))
    assert out == "> Quoted.\n"


def test_bullet_and_ordered_lists():
    bullets = {"type": rt.BULLET_LIST, "content": [
        {"type": rt.LIST_ITEM, "content": [para(text("one"))]},
        {"type": rt.LIST_ITEM, "content": [para(text("two"))]},
    ]}
    assert md(doc(bullets)) == "- one\n- two\n"

    ordered = {"type": rt.ORDERED_LIST, "attrs": {"start": 1}, "content": [
        {"type": rt.LIST_ITEM, "content": [para(text("first"))]},
        {"type": rt.LIST_ITEM, "content": [para(text("second"))]},
    ]}
    assert md(doc(ordered)) == "1. first\n2. second\n"


def test_to_markdown_never_raises_on_garbage():
    """Agents read this output; it must degrade rather than break the pipeline."""
    assert rt.to_markdown(None) == ""
    assert rt.to_markdown({"type": "notadoc"}) == ""
    weird = doc({"type": "somethingNew", "content": [text("kept")]})
    assert "kept" in rt.to_markdown(weird)


# ---------------------------------------------------------------- md -> doc

def test_parses_paragraphs():
    d = rt.from_markdown("One.\n\nTwo.")
    assert [b["type"] for b in d["content"]] == [rt.PARAGRAPH, rt.PARAGRAPH]


def test_parses_heading_levels():
    d = rt.from_markdown("# H1\n\n### H3")
    assert [b["attrs"]["level"] for b in d["content"]] == [1, 3]


def test_parses_setext_headings():
    d = rt.from_markdown("Title\n=====")
    assert d["content"][0]["type"] == rt.HEADING
    assert d["content"][0]["attrs"]["level"] == 1


def test_parses_marks():
    d = rt.from_markdown("**b** and *i* and ~~s~~ and `c`")
    marks = [m["type"] for n in d["content"][0]["content"] for m in n.get("marks", [])]
    assert set(marks) == {"bold", "italic", "strike", "code"}


def test_bold_is_not_read_as_two_italics():
    d = rt.from_markdown("**strong**")
    node = d["content"][0]["content"][0]
    assert node["text"] == "strong"
    assert [m["type"] for m in node["marks"]] == ["bold"]


def test_code_content_is_literal():
    """Markup inside a code span must not be re-parsed."""
    d = rt.from_markdown("`**not bold**`")
    node = d["content"][0]["content"][0]
    assert node["text"] == "**not bold**"
    assert [m["type"] for m in node["marks"]] == ["code"]


def test_parses_links():
    d = rt.from_markdown("[Novel OS](https://x.dev)")
    node = d["content"][0]["content"][0]
    assert node["marks"][0]["attrs"]["href"] == "https://x.dev"


@pytest.mark.parametrize("rule", ["---", "***", "___", "* * *", "- - -"])
def test_parses_scene_breaks(rule):
    d = rt.from_markdown(f"A.\n\n{rule}\n\nB.")
    assert [b["type"] for b in d["content"]] == [
        rt.PARAGRAPH, rt.HORIZONTAL_RULE, rt.PARAGRAPH]


def test_standalone_image_becomes_a_block():
    d = rt.from_markdown("![Lena](/img.png)")
    assert d["content"][0]["type"] == rt.IMAGE
    assert d["content"][0]["attrs"]["alt"] == "Lena"


def test_inline_image_stays_inline():
    d = rt.from_markdown("Before ![x](/i.png) after")
    types = [n["type"] for n in d["content"][0]["content"]]
    assert rt.IMAGE in types and types[0] == rt.TEXT


def test_parses_blockquote_and_lists():
    d = rt.from_markdown("> quoted\n\n- one\n- two\n\n1. first")
    assert [b["type"] for b in d["content"]] == [
        rt.BLOCKQUOTE, rt.BULLET_LIST, rt.ORDERED_LIST]


def test_empty_markdown_yields_an_editable_paragraph():
    assert rt.from_markdown("") == {"type": rt.DOC, "content": [{"type": rt.PARAGRAPH}]}


# ------------------------------------------------------------- round trips

ROUND_TRIP_FIXTURES = [
    "Plain prose.\n",
    "One paragraph.\n\nAnd another.\n",
    "# Chapter One\n\nThe array woke at dawn.\n",
    "She was **certain**, and *he* was not.\n",
    "A scene ended.\n\n---\n\nAnother began.\n",
    "> He said it plainly.\n",
    "- one\n- two\n- three\n",
    "1. first\n2. second\n",
    "![Lena](/api/projects/p/media/abc/raw)\n",
    'Text with ![an image](/i.png "titled") inline.\n',
    "See [the notes](https://example.com) for context.\n",
    "Mixed **bold and *italic*** together.\n",
    "## Heading\n\nBody text.\n\n---\n\n- a\n- b\n",
]


@pytest.mark.parametrize("source", ROUND_TRIP_FIXTURES)
def test_markdown_round_trips(source):
    """md -> doc -> md must be stable, or the agents' view drifts on every save."""
    once = rt.to_markdown(rt.from_markdown(source))
    twice = rt.to_markdown(rt.from_markdown(once))
    assert once == twice, "conversion is not idempotent"
    assert once == source


def test_prose_survives_a_round_trip_verbatim():
    """The words themselves must never change, whatever happens to markup."""
    source = (
        "# The Last Signal\n\n"
        "Lena watched the **array** wake, one dish at a time.\n\n"
        "---\n\n"
        "> *Nothing* out there answers.\n"
    )
    assert rt.to_markdown(rt.from_markdown(source)) == source


# ------------------------------------------------------------------ counting

def test_word_count_ignores_markup():
    d = rt.from_markdown("# Title\n\nThe **quick** brown fox.\n")
    assert rt.word_count(d) == 5  # Title, The, quick, brown, fox.


def test_word_count_of_empty_doc_is_zero():
    assert rt.word_count(rt.empty_doc()) == 0


# ----------------------------------------------------- service + route wiring

def _project(tmp_path):
    import json as _json
    from api.main import create_app
    from fastapi.testclient import TestClient

    root = tmp_path / "projects"
    state_dir = root / "book" / "outputs" / "state"
    state_dir.mkdir(parents=True)
    state_dir.joinpath("story_state.json").write_text(_json.dumps({
        "metadata": {"title": "Book", "genre": "SF", "author": "A"},
        "characters": {}, "plot_threads": {},
        "chapters": {"1": {"number": 1, "title": "One", "status": "drafted"}},
        "timeline": [], "style_profile": {}, "session_log": [],
    }), encoding="utf-8")
    client = TestClient(create_app(
        projects_root=root, db_url=f"sqlite:///{(tmp_path / 'rt.db').as_posix()}"))
    return client, root / "book"


def test_pre_p1_final_converts_from_markdown_on_read(tmp_path):
    """Lazy migration: an existing .md Final opens as rich text untouched."""
    client, proj = _project(tmp_path)
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True)
    original = "# One\n\nShe was **certain**.\n"
    (manuscript / "chapter_001_final.md").write_text(original, encoding="utf-8")

    body = client.get("/api/projects/book/chapters/1/final/doc").json()
    assert body["doc"]["content"][0]["type"] == rt.HEADING
    # "One" + "She was certain." the mark must not split "certain." in two.
    assert body["word_count"] == 4
    # Nothing was rewritten: the file on disk is byte-identical.
    assert (manuscript / "chapter_001_final.md").read_text(encoding="utf-8") == original


def test_saving_a_doc_writes_the_markdown_projection_to_disk(tmp_path):
    """The .md file is what agents read, so it must track every save."""
    client, proj = _project(tmp_path)
    doc_body = rt.from_markdown("The array woke.\n\n---\n\nLena watched.\n")

    resp = client.put("/api/projects/book/chapters/1/final/doc", json={"doc": doc_body})
    assert resp.status_code == 200

    on_disk = (proj / "outputs" / "manuscript" / "chapter_001_final.md").read_text(encoding="utf-8")
    assert on_disk == "The array woke.\n\n---\n\nLena watched.\n"


def test_saved_doc_is_returned_verbatim_not_reparsed(tmp_path):
    """Round-tripping through markdown would lose anything the schema adds later."""
    client, _ = _project(tmp_path)
    doc_body = rt.from_markdown("Hello.")
    client.put("/api/projects/book/chapters/1/final/doc", json={"doc": doc_body})
    assert client.get("/api/projects/book/chapters/1/final/doc").json()["doc"] == doc_body


def test_final_doc_404s_for_unknown_chapter(tmp_path):
    client, _ = _project(tmp_path)
    assert client.get("/api/projects/book/chapters/99/final/doc").status_code == 404


def test_empty_final_opens_as_an_editable_document(tmp_path):
    client, _ = _project(tmp_path)
    body = client.get("/api/projects/book/chapters/1/final/doc").json()
    assert body["doc"] == rt.empty_doc()
    assert body["word_count"] == 0


def test_find_quote_locates_span():
    d = rt.from_markdown("Lena watched the array wake.\n")
    assert rt.find_quote(d, "the array") == (13, 22)


def test_find_quote_missing_is_none():
    d = rt.from_markdown("Nothing here.\n")
    assert rt.find_quote(d, "array") is None


def test_comment_with_quote_gets_anchored(tmp_path):
    client, proj = _project(tmp_path)
    manuscript = proj / "outputs" / "manuscript"
    manuscript.mkdir(parents=True)
    (manuscript / "chapter_001_final.md").write_text(
        "Lena watched the array wake.\n", encoding="utf-8")
    resp = client.post("/api/projects/book/chapters/1/comments", json={
        "body": "Nice beat", "quote": "the array",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["from_pos"] == 13
    assert body["to_pos"] == 22
    assert body["anchor_status"] == "ok"


def test_comment_with_missing_quote_is_unresolved(tmp_path):
    client, _ = _project(tmp_path)
    resp = client.post("/api/projects/book/chapters/1/comments", json={
        "body": "Orphan", "quote": "not in the manuscript",
    })
    assert resp.status_code == 201
    assert resp.json()["anchor_status"] == "unresolved"


# ------------------------------------------------- track changes (P5.1)

def _suggested(t, kind, author="Mriganka"):
    return text(t, {"type": kind, "attrs": {"author": author, "id": "s1"}})


def test_pending_insertion_is_absent_from_the_markdown_agents_read():
    d = doc(para(
        text("She left "),
        _suggested("without looking back", rt.SUGGESTION_INSERT),
        text("."),
    ))
    assert md(d) == "She left .\n"


def test_text_proposed_for_deletion_is_still_in_the_projection():
    """A deletion is a proposal - until accepted the words are still the novel."""
    d = doc(para(
        text("She left "),
        _suggested("quietly ", rt.SUGGESTION_DELETE),
        text("by the pier."),
    ))
    assert md(d) == "She left quietly by the pier.\n"


def test_projection_is_the_reject_all_view():
    d = doc(para(
        _suggested("New. ", rt.SUGGESTION_INSERT),
        text("Kept. "),
        _suggested("Doomed.", rt.SUGGESTION_DELETE),
    ))
    assert md(d) == "Kept. Doomed.\n"


def test_pending_insertions_do_not_inflate_the_word_count():
    d = doc(para(text("one two "), _suggested("three four", rt.SUGGESTION_INSERT)))
    assert rt.word_count(d) == 2


def test_has_suggestions_detects_either_kind():
    assert not rt.has_suggestions(doc(para(text("plain"))))
    assert rt.has_suggestions(doc(para(_suggested("x", rt.SUGGESTION_INSERT))))
    assert rt.has_suggestions(doc(para(_suggested("x", rt.SUGGESTION_DELETE))))


def test_map_text_rewrites_text_without_disturbing_marks():
    d = doc(para(_suggested("a — b", rt.SUGGESTION_INSERT), text("tail")))
    out = rt.map_text(d, lambda s: s.replace("—", "-"))
    node = out["content"][0]["content"][0]
    assert node["text"] == "a - b"
    assert node["marks"][0]["type"] == rt.SUGGESTION_INSERT
    assert node["marks"][0]["attrs"]["author"] == "Mriganka"


def test_saving_a_doc_preserves_pending_suggestions(tmp_path):
    """The save path used to rebuild the doc from markdown, which would drop
    every suggestion because markdown cannot express one."""
    client, proj = _project(tmp_path)
    body = doc(para(
        text("She left "),
        _suggested("without looking back", rt.SUGGESTION_INSERT),
        text("."),
    ))
    resp = client.put("/api/projects/book/chapters/1/final/doc", json={"doc": body})
    assert resp.status_code == 200

    saved = client.get("/api/projects/book/chapters/1/final/doc").json()
    assert rt.has_suggestions(saved["doc"])
    # ...and the file the agents read still shows the reject-all view.
    on_disk = (proj / "outputs" / "manuscript" / "chapter_001_final.md").read_text(
        encoding="utf-8"
    )
    assert "without looking back" not in on_disk
