"""DOCX output, written directly (PLAN.md P6).

A .docx is a ZIP of XML parts. Our block set is narrow - paragraphs, headings,
block quotes, scene breaks, with alignment, size, emphasis and page breaks - so
emitting the WordprocessingML by hand is a few hundred lines and adds **no
dependency**. That matters here: requirements.txt opens by saying to install
only what you actually use, and a writer who exports twice a year should not
carry a document library to do it.

The parts written are the minimum a conforming reader needs:

    [Content_Types].xml   what each part is
    _rels/.rels           points at the main document
    word/document.xml     the manuscript

Units are the awkward part of OOXML and are converted in one place below:
sizes are half-points, spacing and indents are twips (1/20 pt), and line
spacing is 240ths of a line.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from typing import List
from xml.sax.saxutils import escape, quoteattr

from compile_book import CompiledBook, inline_runs
from styles import Style, StyleSheet

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_FONTS = {
    "serif": "Georgia",
    "sans": "Calibri",
    "mono": "Consolas",
}

# Word understands these four; "justify" is spelled "both".
_ALIGN = {"left": "left", "center": "center", "right": "right", "justify": "both"}


def _half_points(pt: float) -> int:
    return max(1, int(round(float(pt) * 2)))


def _twips_from_em(em: float, size_pt: float) -> int:
    """Ems are relative to the type size; a twip is a twentieth of a point."""
    return int(round(float(em) * float(size_pt) * 20))


def _paragraph_properties(style: Style) -> str:
    parts: List[str] = []
    if style.page_break_before:
        parts.append("<w:pageBreakBefore/>")
    parts.append(f'<w:jc w:val="{_ALIGN.get(style.align, "left")}"/>')

    spacing = [
        f'w:before="{_twips_from_em(style.space_before_em, style.size_pt)}"',
        f'w:after="{_twips_from_em(style.space_after_em, style.size_pt)}"',
        # 240ths of a line: Word's "auto" line rule.
        f'w:line="{int(round(float(style.line_height) * 240))}"',
        'w:lineRule="auto"',
    ]
    parts.append(f"<w:spacing {' '.join(spacing)}/>")

    if style.first_line_indent_em:
        parts.append(
            f'<w:ind w:firstLine="{_twips_from_em(style.first_line_indent_em, style.size_pt)}"/>'
        )
    return f"<w:pPr>{''.join(parts)}</w:pPr>"


def _run_properties(style: Style, bold: bool, italic: bool) -> str:
    font = _FONTS.get(style.font, "Georgia")
    parts = [
        f'<w:rFonts w:ascii={quoteattr(font)} w:hAnsi={quoteattr(font)}/>',
        f'<w:sz w:val="{_half_points(style.size_pt)}"/>',
        f'<w:szCs w:val="{_half_points(style.size_pt)}"/>',
    ]
    if style.bold or bold:
        parts.append("<w:b/>")
    if style.italic or italic:
        parts.append("<w:i/>")
    if style.small_caps:
        parts.append("<w:smallCaps/>")
    return f"<w:rPr>{''.join(parts)}</w:rPr>"


def _paragraph(text: str, style: Style) -> str:
    runs = []
    for run in inline_runs(text) or []:
        if not run.text:
            continue
        runs.append(
            f"<w:r>{_run_properties(style, run.bold, run.italic)}"
            # xml:space matters: Word strips leading and trailing spaces without it.
            f'<w:t xml:space="preserve">{escape(run.text)}</w:t></w:r>'
        )
    return f"<w:p>{_paragraph_properties(style)}{''.join(runs)}</w:p>"


def _document(book: CompiledBook, sheet: StyleSheet) -> str:
    body: List[str] = [_paragraph(book.title, sheet.get("title"))]

    byline = " · ".join(p for p in (book.author, book.genre) if p)
    if byline:
        body.append(_paragraph(byline, sheet.get("subtitle")))

    for block in book.blocks:
        style = sheet.get(block.kind)
        text = sheet.scene_break_marker if block.kind == "scene_break" else block.text
        body.append(_paragraph(text, style))

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>{"".join(body)}</w:body></w:document>'
    )


def render_docx(book: CompiledBook, sheet: StyleSheet) -> bytes:
    """A .docx of the compiled manuscript."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", _document(book, sheet))
    return buffer.getvalue()
