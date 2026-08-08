"""ProseMirror document ↔ markdown (PLAN.md P1).

Final text becomes rich text so track changes, styles, text-anchored comments
and inline images are possible at all. But the five agents read markdown, and
`core/orchestrator.py` reads and writes `chapter_NNN_*.md` from disk. Rewriting
the agent side to understand a document model would be a large change to the
part of the system that is working best.

So: **ProseMirror JSON is canonical, markdown is a projection.** Every save
serialises the document back to markdown and writes the `.md` file the engine
already expects. Agent prompts are untouched. The markdown file also doubles as
a plain-text fallback, so a bad conversion can never destroy a manuscript.

The schema is deliberately small it covers what a novel needs and nothing
more. A narrow schema is what makes round-tripping predictable; every node here
has an unambiguous markdown form.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

DOC = "doc"
PARAGRAPH = "paragraph"
HEADING = "heading"
BLOCKQUOTE = "blockquote"
BULLET_LIST = "bulletList"
ORDERED_LIST = "orderedList"
LIST_ITEM = "listItem"
HORIZONTAL_RULE = "horizontalRule"
IMAGE = "image"
HARD_BREAK = "hardBreak"
TEXT = "text"

# Mark name -> the markdown delimiter that wraps it.
MARK_DELIMITERS = {
    "bold": "**",
    "italic": "*",
    "strike": "~~",
    "code": "`",
}

# Scene break. The style profile's marker is "***", but a horizontal rule is
# the semantic node; markdown emits "---" and both parse back to the same thing.
SCENE_BREAK = "---"

_SETEXT_H1 = re.compile(r"^=+\s*$")
_SETEXT_H2 = re.compile(r"^-{2,}\s*$")


def empty_doc() -> Dict[str, Any]:
    return {"type": DOC, "content": [{"type": PARAGRAPH}]}


# ============================================================ doc -> markdown

def to_markdown(doc: Optional[Dict[str, Any]]) -> str:
    """Serialise a ProseMirror document to markdown.

    This is the projection agents read, so it must never raise on a malformed
    document an unknown node degrades to its text content rather than
    breaking the pipeline.
    """
    if not doc or doc.get("type") != DOC:
        return ""
    blocks = [_block_to_md(node) for node in doc.get("content") or []]
    return "\n\n".join(b for b in blocks if b is not None).strip() + "\n" if blocks else ""


def _block_to_md(node: Dict[str, Any], depth: int = 0) -> Optional[str]:
    ntype = node.get("type")

    if ntype == PARAGRAPH:
        return _inline_to_md(node.get("content") or [])

    if ntype == HEADING:
        level = max(1, min(6, int((node.get("attrs") or {}).get("level", 1))))
        return f"{'#' * level} {_inline_to_md(node.get('content') or [])}"

    if ntype == BLOCKQUOTE:
        inner = "\n\n".join(
            b for b in (_block_to_md(c, depth) for c in node.get("content") or [])
            if b is not None
        )
        return "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))

    if ntype in (BULLET_LIST, ORDERED_LIST):
        return _list_to_md(node, depth)

    if ntype == HORIZONTAL_RULE:
        return SCENE_BREAK

    if ntype == IMAGE:
        return _image_to_md(node)

    # Unknown block: fall back to whatever text it carries rather than dropping
    # the author's words.
    return _inline_to_md(node.get("content") or [])


def _list_to_md(node: Dict[str, Any], depth: int) -> str:
    ordered = node.get("type") == ORDERED_LIST
    start = int((node.get("attrs") or {}).get("start", 1)) if ordered else 1
    pad = "  " * depth
    lines: List[str] = []

    for i, item in enumerate(node.get("content") or []):
        marker = f"{start + i}." if ordered else "-"
        parts = [
            b for b in (_block_to_md(c, depth + 1) for c in item.get("content") or [])
            if b is not None
        ]
        body = "\n\n".join(parts) if parts else ""
        first, *rest = body.split("\n") if body else [""]
        lines.append(f"{pad}{marker} {first}".rstrip())
        # Continuation lines indent under the marker so nesting survives.
        lines.extend(f"{pad}  {line}".rstrip() for line in rest)
    return "\n".join(lines)


def _image_to_md(node: Dict[str, Any]) -> str:
    attrs = node.get("attrs") or {}
    src = attrs.get("src") or ""
    alt = (attrs.get("alt") or "").replace("]", r"\]")
    title = attrs.get("title") or ""
    suffix = f' "{title}"' if title else ""
    return f"![{alt}]({src}{suffix})"


def _inline_to_md(nodes: List[Dict[str, Any]]) -> str:
    out: List[str] = []
    for node in nodes:
        ntype = node.get("type")
        if ntype == HARD_BREAK:
            out.append("  \n")
        elif ntype == IMAGE:
            out.append(_image_to_md(node))
        elif ntype == TEXT:
            out.append(_text_to_md(node))
        elif node.get("content"):
            out.append(_inline_to_md(node["content"]))
    return "".join(out)


def _text_to_md(node: Dict[str, Any]) -> str:
    text = node.get("text") or ""
    marks = node.get("marks") or []
    if not marks:
        return text

    link_href = None
    codex = None
    # Apply innermost-first so nesting reads naturally: **_text_**.
    for mark in marks:
        name = mark.get("type")
        if name == "link":
            link_href = (mark.get("attrs") or {}).get("href", "")
            continue
        if name == "codexMention":
            attrs = mark.get("attrs") or {}
            eid = attrs.get("entryId") or attrs.get("entry_id") or ""
            etype = attrs.get("entryType") or attrs.get("entry_type") or "character"
            if eid:
                codex = (etype, eid)
            continue
        delim = MARK_DELIMITERS.get(name)
        if delim:
            text = f"{delim}{text}{delim}"
    if codex is not None:
        etype, eid = codex
        text = f"[{text}](codex://{etype}/{eid})"
    elif link_href is not None:
        text = f"[{text}]({link_href})"
    return text


# ============================================================ markdown -> doc

_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^\s)]+)(?:\s+\"(?P<title>[^\"]*)\")?\)")
_LINK_RE = re.compile(r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<href>[^\s)]+)\)")
_BOLD_RE = re.compile(r"\*\*(?P<t>.+?)\*\*", re.S)
_ITALIC_RE = re.compile(r"(?<!\*)\*(?P<t>[^*]+?)\*(?!\*)", re.S)
_STRIKE_RE = re.compile(r"~~(?P<t>.+?)~~", re.S)
_CODE_RE = re.compile(r"`(?P<t>[^`]+?)`")

_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*)$")
_HR_RE = re.compile(r"^\s*(?:\*\s*\*\s*\*[\s*]*|-\s*-\s*-[\s-]*|_\s*_\s*_[\s_]*)$")
_BULLET_RE = re.compile(r"^(?P<indent>\s*)[-*+]\s+(?P<text>.*)$")
_ORDERED_RE = re.compile(r"^(?P<indent>\s*)(?P<num>\d+)[.)]\s+(?P<text>.*)$")
_QUOTE_RE = re.compile(r"^\s*>\s?(?P<text>.*)$")


def from_markdown(text: str) -> Dict[str, Any]:
    """Parse markdown into a ProseMirror document.

    Used to migrate existing `.md` finals into the rich-text editor. Anything
    the small schema does not model stays as literal text rather than being
    silently dropped a manuscript must survive a conversion it doesn't fully
    understand.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    content: List[Dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if _HR_RE.match(line):
            content.append({"type": HORIZONTAL_RULE})
            i += 1
            continue

        m = _HEADING_RE.match(line)
        if m:
            content.append({
                "type": HEADING,
                "attrs": {"level": len(m.group("hashes"))},
                "content": _parse_inline(m.group("text").strip()),
            })
            i += 1
            continue

        if _QUOTE_RE.match(line):
            block, i = _consume_quote(lines, i)
            content.append(block)
            continue

        if _BULLET_RE.match(line) or _ORDERED_RE.match(line):
            block, i = _consume_list(lines, i)
            content.append(block)
            continue

        # A lone image on its own line is a block, not an inline run.
        stripped = line.strip()
        only_image = _IMAGE_RE.fullmatch(stripped)
        if only_image:
            content.append(_image_node(only_image))
            i += 1
            continue

        para, i = _consume_paragraph(lines, i)
        if para is not None:
            content.append(para)

    return {"type": DOC, "content": content or [{"type": PARAGRAPH}]}


def _image_node(m: "re.Match[str]") -> Dict[str, Any]:
    attrs: Dict[str, Any] = {"src": m.group("src"), "alt": m.group("alt") or ""}
    if m.group("title"):
        attrs["title"] = m.group("title")
    return {"type": IMAGE, "attrs": attrs}


def _consume_paragraph(lines: List[str], i: int) -> tuple[Optional[Dict[str, Any]], int]:
    buf: List[str] = []
    while i < len(lines):
        line = lines[i]
        if (not line.strip() or _HR_RE.match(line) or _HEADING_RE.match(line)
                or _QUOTE_RE.match(line) or _BULLET_RE.match(line)
                or _ORDERED_RE.match(line)):
            break
        # A setext underline turns the buffered line into a heading.
        if buf and _SETEXT_H1.match(line):
            return ({"type": HEADING, "attrs": {"level": 1},
                     "content": _parse_inline(" ".join(buf).strip())}, i + 1)
        if buf and _SETEXT_H2.match(line) and not _HR_RE.match(line):
            return ({"type": HEADING, "attrs": {"level": 2},
                     "content": _parse_inline(" ".join(buf).strip())}, i + 1)
        buf.append(line.rstrip())
        i += 1

    if not buf:
        return None, i + 1
    return {"type": PARAGRAPH, "content": _parse_inline(" ".join(buf).strip())}, i


def _consume_quote(lines: List[str], i: int) -> tuple[Dict[str, Any], int]:
    buf: List[str] = []
    while i < len(lines):
        m = _QUOTE_RE.match(lines[i])
        if not m:
            break
        buf.append(m.group("text"))
        i += 1
    inner = from_markdown("\n".join(buf))
    return {"type": BLOCKQUOTE, "content": inner.get("content") or []}, i


def _consume_list(lines: List[str], i: int) -> tuple[Dict[str, Any], int]:
    first = lines[i]
    ordered = bool(_ORDERED_RE.match(first))
    pattern = _ORDERED_RE if ordered else _BULLET_RE
    base_indent = len(pattern.match(first).group("indent"))

    items: List[Dict[str, Any]] = []
    start = int(_ORDERED_RE.match(first).group("num")) if ordered else 1

    while i < len(lines):
        line = lines[i]
        m = pattern.match(line)
        if not m or len(m.group("indent")) < base_indent:
            # A different marker at the same level ends this list.
            break
        if len(m.group("indent")) > base_indent:
            # Nested list: recurse and attach to the previous item.
            nested, i = _consume_list(lines, i)
            if items:
                items[-1]["content"].append(nested)
            continue
        items.append({
            "type": LIST_ITEM,
            "content": [{"type": PARAGRAPH, "content": _parse_inline(m.group("text"))}],
        })
        i += 1

    node: Dict[str, Any] = {
        "type": ORDERED_LIST if ordered else BULLET_LIST,
        "content": items,
    }
    if ordered:
        node["attrs"] = {"start": start}
    return node, i


def _parse_inline(text: str) -> List[Dict[str, Any]]:
    """Split a line into text nodes carrying marks.

    Handled in precedence order so `**bold**` is not mistaken for two italics.
    """
    if not text:
        return []
    return _apply(text, [])


def _apply(text: str, marks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Order matters. Images and links are structural, so they bind outermost.
    # Code comes next because its content is literal without this, the bold
    # in `**not bold**` would match before the code span did. Emphasis last,
    # bold before italic so ** is never read as two single asterisks.
    for regex, mark in (
        (_IMAGE_RE, None),           # images are nodes, not marks
        (_LINK_RE, "link"),
        (_CODE_RE, "code"),
        (_BOLD_RE, "bold"),
        (_STRIKE_RE, "strike"),
        (_ITALIC_RE, "italic"),
    ):
        m = regex.search(text)
        if not m:
            continue

        before = _apply(text[:m.start()], marks) if m.start() else []
        after = _apply(text[m.end():], marks) if m.end() < len(text) else []

        if regex is _IMAGE_RE:
            middle: List[Dict[str, Any]] = [_image_node(m)]
        elif mark == "link":
            href = m.group("href") or ""
            if href.startswith("codex://"):
                rest = href[len("codex://"):]
                parts = rest.split("/", 1)
                etype = parts[0] if parts else "character"
                eid = parts[1] if len(parts) > 1 else ""
                inner_marks = marks + [{
                    "type": "codexMention",
                    "attrs": {"entryId": eid, "entryType": etype},
                }]
            else:
                inner_marks = marks + [{"type": "link", "attrs": {"href": href}}]
            middle = _apply(m.group("text"), inner_marks)
        elif mark == "code":
            # Code is literal: no further mark parsing inside it.
            middle = [_text_node(m.group("t"), marks + [{"type": "code"}])]
        else:
            middle = _apply(m.group("t"), marks + [{"type": mark}])

        return before + middle + after

    return [_text_node(text, marks)] if text else []


def _text_node(text: str, marks: List[Dict[str, Any]]) -> Dict[str, Any]:
    node: Dict[str, Any] = {"type": TEXT, "text": text}
    if marks:
        node["marks"] = list(marks)
    return node


# ================================================================== utilities

_BLOCK_TYPES = {
    DOC, PARAGRAPH, HEADING, BLOCKQUOTE, BULLET_LIST, ORDERED_LIST,
    LIST_ITEM, HORIZONTAL_RULE, IMAGE,
}


def word_count(doc: Optional[Dict[str, Any]]) -> int:
    """Count words in a document, ignoring markup entirely."""
    return len(_plain_text(doc).split())


def plain_text(doc: Optional[Dict[str, Any]]) -> str:
    """Flatten a document to plain text (for quote ↔ position backfill)."""
    return _plain_text(doc).strip()


def find_quote(doc: Optional[Dict[str, Any]], quote: str) -> Optional[tuple[int, int]]:
    """Best-effort locate a quote in the plain-text projection.

    Returns (from, to) character offsets into `plain_text(doc)`, or None if the
    quote is missing or empty. Used to backfill pre-P1 comments that only stored
    a quote string.
    """
    q = (quote or "").strip()
    if not q:
        return None
    hay = plain_text(doc)
    idx = hay.find(q)
    if idx < 0:
        return None
    return idx, idx + len(q)


def _plain_text(node: Any) -> str:
    """Flatten to plain text.

    Sibling text nodes are concatenated rather than space-joined: a mark splits
    a sentence into several nodes, and `**certain**.` must stay one word rather
    than becoming "certain" plus a stray ".". Only block boundaries introduce
    whitespace.
    """
    if isinstance(node, list):
        return "".join(_plain_text(c) for c in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == TEXT:
        return node.get("text") or ""
    inner = "".join(_plain_text(c) for c in node.get("content") or [])
    return f"{inner}\n" if node.get("type") in _BLOCK_TYPES else inner
