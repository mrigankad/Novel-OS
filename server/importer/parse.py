"""Turn a manuscript file into chapters.

    book = parse_manuscript(data, "my-novel.docx")
    book.chapters -> [ParsedChapter(title, act, text, words)], book.detected_by, book.warnings

Every format is first reduced to a flat list of blocks, then one assembler
splits them into chapters, so the rules (acts, empty sections, front matter)
are the same whatever the source.

Blocks: ("heading", title) starts a chapter, ("act", label) starts a part/act,
("para", text) is prose (Markdown, italics as *...*), ("break", "") is a scene break.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

from core.prose_sanitize import strip_state_blocks

from ..services.book import word_count

MAX_BYTES = 25 * 1024 * 1024
EXTENSIONS = (".docx", ".md", ".markdown", ".txt", ".epub")
SCENE_BREAK = "* * *"
PREAMBLE_KEEP_WORDS = 150  # front matter shorter than this is dropped (title pages, dedications)


class ImportError_(ValueError):
    """The file can't be imported (bad type, corrupt, empty)."""


@dataclass
class ParsedChapter:
    title: str
    act: int
    text: str
    words: int = 0

    def as_dict(self, number: int) -> dict:
        return {"number": number, "title": self.title, "act": self.act, "words": self.words}


@dataclass
class ParsedBook:
    chapters: list[ParsedChapter]
    detected_by: str
    warnings: list[str] = field(default_factory=list)
    title: str = ""

    @property
    def words(self) -> int:
        return sum(c.words for c in self.chapters)

    def report(self) -> dict:
        return {"chapters": [c.as_dict(i) for i, c in enumerate(self.chapters, 1)], "words": self.words,
                "detected_by": self.detected_by, "warnings": self.warnings, "title": self.title}


# --------------------------------------------------------------- heading rules

CHAPTER_RE = re.compile(r"^(chapter|ch\.?)\s+([\w-]+)\s*[:.\-–—]?\s*(.*)$", re.I)
ACT_RE = re.compile(r"^(part|act)\s+([\w-]+)\s*[:.\-–—]?\s*(.*)$", re.I)
BREAK_RE = re.compile(r"^\s*(?:(?:\*\s*){3,}|#|(?:-\s*){3,}|~{3,})\s*$")
MAX_HEADING_CHARS = 80

_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
          "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


def _number(token: str) -> int | None:
    t = token.strip().lower()
    if t.isdigit():
        return int(t)
    if t in _WORDS:
        return _WORDS.index(t)
    if t and all(ch in _ROMAN for ch in t):
        total = 0
        for i, ch in enumerate(t):
            v = _ROMAN[ch]
            total += -v if i + 1 < len(t) and _ROMAN[t[i + 1]] > v else v
        return total or None
    return None


def classify_line(line: str) -> tuple[str, str] | None:
    """('act', label) / ('heading', title) for a heading-looking line, else None."""
    s = line.strip().strip("*_").strip()
    if not s or len(s) > MAX_HEADING_CHARS:
        return None
    if ACT_RE.match(s):
        return ("act", s)
    m = CHAPTER_RE.match(s)
    if m:
        if s.endswith((".", ",", ";")) and not m.group(3) and _number(m.group(2)) is None:
            return None  # "Chapter and verse." is prose, not a heading
        if _number(m.group(2)) is None and not m.group(2)[0].isupper():
            return None
        return ("heading", m.group(3).strip() or s)
    return None


def _clean_heading(text: str) -> str:
    """'Chapter 3: The Bridge' -> 'The Bridge'; 'Chapter One' stays as is."""
    s = text.strip().strip("#").strip().strip("*_").strip()
    m = CHAPTER_RE.match(s)
    if m and m.group(3).strip():
        return m.group(3).strip()
    return s


# --------------------------------------------------------------- assembler

def assemble(blocks: list[tuple[str, str]], detected_by: str, warnings: list[str] | None = None) -> ParsedBook:
    warnings = list(warnings or [])
    chapters: list[dict] = []
    preamble: list[str] = []
    cur: dict | None = None
    act = 1
    acts_seen = 0

    def close():
        nonlocal cur
        if cur is not None:
            chapters.append(cur)
        cur = None

    for kind, text in blocks:
        if kind == "act":
            close()
            acts_seen += 1
            m = ACT_RE.match(text.strip())
            n = _number(m.group(2)) if m else None
            act = n if n and n > 0 else acts_seen
        elif kind == "heading":
            close()
            cur = {"title": _clean_heading(text), "act": act, "paras": []}
        elif kind == "break":
            if cur is not None and cur["paras"] and cur["paras"][-1] != SCENE_BREAK:
                cur["paras"].append(SCENE_BREAK)
        elif text.strip():
            (cur["paras"] if cur is not None else preamble).append(text.strip())
    close()

    out: list[ParsedChapter] = []
    for c in chapters:
        paras = c["paras"]
        while paras and paras[-1] == SCENE_BREAK:
            paras.pop()
        body = "\n\n".join(paras)
        if not body.strip():
            warnings.append(f"Skipped empty section “{c['title'] or 'untitled'}”")
            continue
        out.append(ParsedChapter(c["title"] or f"Chapter {len(out) + 1}", c["act"], body, word_count(body)))

    pre = "\n\n".join(preamble)
    pre_words = word_count(pre)
    if not out:
        if pre_words:
            out = [ParsedChapter("Chapter 1", 1, pre, pre_words)]
            detected_by = "single"
            warnings.append("No chapter breaks found; imported as a single chapter")
    elif pre_words >= PREAMBLE_KEEP_WORDS:
        out.insert(0, ParsedChapter("Opening", out[0].act, pre, pre_words))
        warnings.append(f"Kept {pre_words} words before the first chapter as “Opening”")
    elif pre_words:
        warnings.append(f"Skipped {pre_words} words of front matter before the first chapter")
    if not out:
        raise ImportError_("No text found in this file")
    return ParsedBook(out, detected_by, warnings)


# --------------------------------------------------------------- docx

def _docx_paragraph_text(p) -> str:
    """Runs to Markdown, italic runs wrapped in *...* (whitespace kept outside the stars)."""
    groups: list[list] = []
    for r in p.runs:
        it = bool(r.italic) or bool(r.style is not None and r.style.font is not None and r.style.font.italic)
        if groups and groups[-1][0] == it:
            groups[-1][1] += r.text
        else:
            groups.append([it, r.text])
    if not groups:
        return p.text
    parts: list[str] = []
    for it, txt in groups:
        if it and txt.strip():
            lead = txt[: len(txt) - len(txt.lstrip())]
            trail = txt[len(txt.rstrip()):]
            parts.append(f"{lead}*{txt.strip()}*{trail}")
        else:
            parts.append(txt)
    return "".join(parts)


def parse_docx(data: bytes) -> ParsedBook:
    try:
        import docx  # python-docx
        d = docx.Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - any parse failure is a bad file
        raise ImportError_(f"Couldn't read this .docx: {e}") from e
    blocks: list[tuple[str, str]] = []
    by_style = by_line = False
    title = ""
    for p in d.paragraphs:
        raw = p.text.strip()
        if not raw:
            continue
        style = (p.style.name if p.style is not None else "") or ""
        if style == "Title":
            title = title or raw
            continue
        if BREAK_RE.match(raw):
            blocks.append(("break", ""))
            continue
        if style in ("Heading 1", "Heading 2"):
            by_style = True
            blocks.append(("act", raw) if ACT_RE.match(raw) else ("heading", raw))
            continue
        hit = classify_line(raw)
        if hit:
            by_line = True
            blocks.append(hit)
            continue
        blocks.append(("para", _docx_paragraph_text(p)))
    book = assemble(blocks, "headings" if by_style else "chapter_lines" if by_line else "single")
    book.title = title
    return book


# --------------------------------------------------------------- markdown / text

def parse_markdown(text: str) -> ParsedBook:
    text = strip_state_blocks(text)
    blocks: list[tuple[str, str]] = []
    buf: list[str] = []
    found = False
    title = ""

    def flush():
        if buf:
            blocks.append(("para", " ".join(x.strip() for x in buf)))
            buf.clear()

    for line in text.splitlines():
        m = re.match(r"^(#{1,2})\s+(.+?)\s*#*\s*$", line)
        if m:
            flush()
            label = m.group(2).strip()
            found = True
            blocks.append(("act", label) if ACT_RE.match(label) else ("heading", label))
            continue
        if BREAK_RE.match(line) and line.strip() != "#":
            flush()
            blocks.append(("break", ""))
            continue
        if not line.strip():
            flush()
            continue
        buf.append(line)
    flush()
    # "# Book Title" followed straight by "## Chapter 1": the empty top heading is the book's title.
    if len(blocks) > 1 and blocks[0][0] == "heading" and blocks[1][0] in ("heading", "act"):
        title = blocks.pop(0)[1]
    if not found:
        return parse_text(text)
    book = assemble(blocks, "headings")
    book.title = title
    return book


def parse_text(text: str) -> ParsedBook:
    text = strip_state_blocks(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    has_chapters = any((classify_line(x) or ("", ""))[0] == "heading" for x in lines)
    blocks: list[tuple[str, str]] = []
    buf: list[str] = []
    blank = 0
    # One paragraph per line when the file never uses blank lines between paragraphs.
    single_line_paras = not any(not x.strip() for x in lines[1:-1]) and len(lines) > 3

    def flush():
        if buf:
            blocks.append(("para", " ".join(x.strip() for x in buf)))
            buf.clear()

    for line in lines:
        if not line.strip():
            blank += 1
            flush()
            continue
        if blank >= 3:
            blocks.append(("sep", ""))
        blank = 0
        hit = classify_line(line)
        if hit:
            flush()
            blocks.append(hit)
            continue
        if BREAK_RE.match(line):
            flush()
            blocks.append(("sep", ""))
            continue
        buf.append(line)
        if single_line_paras:
            flush()
    flush()

    if has_chapters:
        return assemble([("break", "") if k == "sep" else (k, t) for k, t in blocks], "chapter_lines")
    if any(k == "sep" for k, _ in blocks):
        out: list[tuple[str, str]] = [("heading", "")]
        for k, t in blocks:
            out.append(("heading", "") if k == "sep" else (k, t))
        book = assemble(out, "separators")
        book.warnings = [w for w in book.warnings if not w.startswith("Skipped empty")]
        for i, c in enumerate(book.chapters, 1):
            c.title = f"Chapter {i}"
        return book
    return assemble(blocks, "single")


# --------------------------------------------------------------- epub

class _HtmlBlocks(HTMLParser):
    BLOCK = {"p", "div", "blockquote", "li"}
    HEAD = {"h1", "h2"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self.title = ""
        self._buf: list[str] = []
        self._in: str | None = None
        self._skip = 0
        self._in_title = False

    def _flush(self):
        txt = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        txt = re.sub(r"\*\s*\*", "", txt)
        if txt:
            kind = "heading" if self._in in self.HEAD else "para"
            if kind == "heading" and ACT_RE.match(txt.strip("*")):
                kind = "act"
            if kind == "para" and BREAK_RE.match(txt):
                kind, txt = "break", ""
            self.blocks.append((kind, txt.strip("*") if kind != "para" else txt))
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.HEAD or tag in self.BLOCK:
            self._flush()
            self._in = tag
        elif tag in ("em", "i"):
            self._buf.append("*")
        elif tag == "br":
            self._buf.append(" ")
        elif tag == "hr":
            self._flush()
            self.blocks.append(("break", ""))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self.HEAD or tag in self.BLOCK:
            self._flush()
            self._in = None
        elif tag in ("em", "i"):
            self._buf.append("*")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and self._in is not None:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def _xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_epub(data: bytes) -> ParsedBook:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        container = _xml(z.read("META-INF/container.xml"))
        opf_path = next(e.get("full-path") for e in container.iter() if _local(e.tag) == "rootfile")
        opf = _xml(z.read(opf_path))
    except Exception as e:  # noqa: BLE001
        raise ImportError_(f"Couldn't read this .epub: {e}") from e
    base = posixpath.dirname(opf_path)
    manifest = {e.get("id"): e for e in opf.iter() if _local(e.tag) == "item"}
    spine = [e.get("idref") for e in opf.iter() if _local(e.tag) == "itemref"]
    title = next((e.text or "" for e in opf.iter() if _local(e.tag) == "title"), "").strip()

    blocks: list[tuple[str, str]] = []
    for idref in spine:
        item = manifest.get(idref)
        if item is None or "nav" in (item.get("properties") or ""):
            continue
        href = posixpath.normpath(posixpath.join(base, item.get("href") or ""))
        try:
            html = z.read(href).decode("utf-8", errors="replace")
        except KeyError:
            continue
        p = _HtmlBlocks()
        p.feed(html)
        p.close()
        doc = p.blocks
        if not any(k == "para" for k, _ in doc):
            # Cover, title page or a part divider: keep only act markers.
            blocks.extend(b for b in doc if b[0] == "act")
            continue
        if not doc or doc[0][0] not in ("heading", "act"):
            doc = [("heading", p.title.strip())] + doc
        elif doc[0][0] == "act":
            doc = [doc[0], ("heading", p.title.strip())] + doc[1:]
        blocks.extend(doc)
    book = assemble(blocks, "epub_spine")
    book.title = title
    return book


# --------------------------------------------------------------- entry point

def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_manuscript(data: bytes, filename: str) -> ParsedBook:
    name = (filename or "").lower()
    ext = next((e for e in EXTENSIONS if name.endswith(e)), "")
    if not ext:
        raise ImportError_("Import a .docx, .md, .txt or .epub file")
    if len(data) > MAX_BYTES:
        raise ImportError_("That file is over 25 MB")
    if not data:
        raise ImportError_("That file is empty")
    if ext == ".docx":
        book = parse_docx(data)
    elif ext == ".epub":
        book = parse_epub(data)
    elif ext in (".md", ".markdown"):
        book = parse_markdown(_decode(data))
    else:
        book = parse_text(_decode(data))
    if not book.title:
        stem = re.sub(r"[_-]+", " ", (filename or "").rsplit("/", 1)[-1].rsplit(".", 1)[0]).strip()
        book.title = stem[:1].upper() + stem[1:] if stem else "Imported manuscript"
    return book
