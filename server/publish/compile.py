"""Compile the manuscript from DB chapters with the core renderers."""

from __future__ import annotations

import io
import re

from sqlmodel import Session, func, select

from ..models import Chapter, Project
from . import ensure_core_path

FORMATS = ("epub", "docx", "html", "md", "pdf")
CONTENT_TYPES = {
    "epub": "application/epub+zip",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "pdf": "application/pdf",
}


def chapter_texts(session: Session, project_id: str) -> list[dict]:
    rows = session.exec(
        select(Chapter.number, Chapter.title, Chapter.text)
        .where(Chapter.project_id == project_id).order_by(Chapter.number)
    ).all()
    return [{"number": n, "title": t, "text": x} for n, t, x in rows]


def total_words(session: Session, project_id: str) -> int:
    return int(session.exec(
        select(func.coalesce(func.sum(Chapter.word_count), 0)).where(Chapter.project_id == project_id)
    ).one())


def build(session: Session, project: Project):
    ensure_core_path()
    from compile_book import gather  # type: ignore[import-not-found]
    from styles import StyleSheet  # type: ignore[import-not-found]

    book = gather(title=project.title, author=project.author, genre=project.genre,
                  chapters=chapter_texts(session, project.id))
    sheet = StyleSheet.from_dict((project.bible or {}).get("stylesheet") or {})
    return book, sheet


def filename(project: Project, fmt: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", project.title or "book").strip("-").lower() or "book"
    return f"{slug}.{fmt}"


def render(session: Session, project: Project, fmt: str) -> bytes:
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}")
    book, sheet = build(session, project)
    if fmt == "pdf":
        return render_pdf(book, sheet)
    from compile_book import render_bytes  # type: ignore[import-not-found]

    return render_bytes(book, sheet, "markdown" if fmt == "md" else fmt)


def render_pdf(book, sheet, trim: tuple[float, float] = (5.5, 8.5)) -> bytes:
    """Simple print interior. Raises ImportError when reportlab is missing."""
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    from compile_book import inline_runs  # type: ignore[import-not-found]

    pt = 72
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(trim[0] * pt, trim[1] * pt), leftMargin=0.75 * pt,
                            rightMargin=0.6 * pt, topMargin=0.7 * pt, bottomMargin=0.7 * pt,
                            title=book.title, author=book.author)
    align = {"center": TA_CENTER, "justify": TA_JUSTIFY, "left": TA_LEFT}

    def style(role: str) -> ParagraphStyle:
        s = sheet.get(role)
        font = {"serif": "Times", "sans": "Helvetica"}.get(s.font, "Times")
        base = {(False, False): f"{font}-Roman" if font == "Times" else font,
                (True, False): f"{font}-Bold", (False, True): f"{font}-Italic" if font == "Times" else f"{font}-Oblique",
                (True, True): f"{font}-BoldItalic" if font == "Times" else f"{font}-BoldOblique"}
        size = min(s.size_pt, 11.0) if role in ("body", "first_paragraph", "block_quote") else s.size_pt
        return ParagraphStyle(role, fontName=base[(s.bold, s.italic)], fontSize=size,
                              leading=size * s.line_height, alignment=align.get(s.align, TA_LEFT),
                              firstLineIndent=s.first_line_indent_em * size,
                              spaceBefore=s.space_before_em * size, spaceAfter=s.space_after_em * size)

    def markup(text: str) -> str:
        parts = []
        for r in inline_runs(text):
            t = r.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if r.bold:
                t = f"<b>{t}</b>"
            if r.italic:
                t = f"<i>{t}</i>"
            parts.append(t)
        return "".join(parts)

    cache: dict[str, ParagraphStyle] = {}
    story: list = [Spacer(1, 2 * pt), Paragraph(markup(book.title), style("title"))]
    if book.author:
        story.append(Paragraph(markup(book.author), style("subtitle")))
    for blk in book.blocks:
        st = cache.setdefault(blk.kind, style(blk.kind))
        if blk.kind == "chapter_title":
            story.append(PageBreak())
            story.append(Paragraph(markup(blk.text), st))
        elif blk.kind == "scene_break":
            story.append(Paragraph(sheet.scene_break_marker, st))
        else:
            story.append(Paragraph(markup(blk.text), st))
    doc.build(story)
    return buf.getvalue()
