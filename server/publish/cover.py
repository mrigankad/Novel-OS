"""Cover studio maths, preflight and export.

All dimensions are inches. Coordinates in ``barcode_box`` are measured from the
top-left corner of the full wrap (bleed included), matching how the web stage
lays the wrap out in CSS.
"""

from __future__ import annotations

import io
import math
from dataclasses import asdict, dataclass
from typing import Optional

BLEED = 0.125
SAFE = 0.125  # KDP: keep live content 0.125 in inside the trim
# Recommended margin for back copy and spine text, a touch more generous than the KDP floor.
TEXT_MARGIN = 0.375
# KDP hardcover case laminate wraps the board: extra 0.51 in "wrap" per side instead of bleed.
HARDCOVER_WRAP = 0.51

PAPER = {"white": 0.002252, "cream": 0.0025, "color": 0.002347}
WORDS_PER_PAGE = {"5.5x8.5": 250, "6x9": 300}
BASE_TRIM = (5.5, 8.5)
TRIMS = ("5x8", "5.25x8", "5.5x8.5", "6x9", "7x10", "8.5x11")
FORMATS = ("ebook", "paperback", "hardcover", "audiobook")
SPINE_TEXT_MIN_PAGES = 100
MIN_PAGES = 24
BARCODE_W, BARCODE_H = 2.0, 1.2
EBOOK_PX = (1600, 2560)
AUDIO_PX = (2400, 2400)
CHARS_PER_SQ_IN = 55  # 11 pt serif, ~1.35 leading


def parse_trim(trim: str) -> tuple[float, float]:
    try:
        w, h = (float(x) for x in (trim or "").lower().replace(" ", "").split("x"))
    except ValueError:
        raise ValueError(f"Trim must look like 5.5x8.5, got {trim!r}")
    if not (3 <= w <= 12 and 3 <= h <= 14):
        raise ValueError("Trim size is outside what printers accept.")
    return w, h


def words_per_page(trim: str) -> float:
    if trim in WORDS_PER_PAGE:
        return WORDS_PER_PAGE[trim]
    w, h = parse_trim(trim)
    return WORDS_PER_PAGE["5.5x8.5"] * (w * h) / (BASE_TRIM[0] * BASE_TRIM[1])


def estimate_pages(words: int, trim: str) -> int:
    """Interior pages from word count, rounded up to an even count, KDP minimum 24."""
    pages = math.ceil(max(0, words) / words_per_page(trim))
    pages = max(MIN_PAGES, pages)
    return pages + (pages % 2)


def spine_width(pages: int, paper: str) -> float:
    if paper not in PAPER:
        raise ValueError(f"Paper must be one of {', '.join(PAPER)}")
    return round(pages * PAPER[paper], 4)


@dataclass
class CoverSpec:
    format: str
    trim: str
    paper: str
    pages: int
    pages_source: str  # "auto" | "manual"
    words: int
    trim_w_in: float
    trim_h_in: float
    bleed_in: float
    spine_in: float
    wrap_w_in: float
    wrap_h_in: float
    safe_margin_in: float
    spine_text_allowed: bool
    barcode_box: Optional[dict]
    pixels: Optional[dict]  # for ebook / audiobook: target pixel size

    def to_dict(self) -> dict:
        return asdict(self)


def compute_spec(*, fmt: str = "paperback", trim: str = "5.5x8.5", paper: str = "cream",
                 words: int = 0, pages: Optional[int] = None) -> CoverSpec:
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}")
    tw, th = parse_trim(trim)
    n_pages = int(pages) if pages else estimate_pages(words, trim)
    source = "manual" if pages else "auto"
    if fmt == "ebook":
        # 1:1.6 front cover only. Report inches at 256 ppi so 1600x2560 px is 6.25x10.
        return CoverSpec(fmt, trim, paper, n_pages, source, words, 6.25, 10.0, 0.0, 0.0, 6.25, 10.0,
                         SAFE, False, None, {"w": EBOOK_PX[0], "h": EBOOK_PX[1]})
    if fmt == "audiobook":
        return CoverSpec(fmt, trim, paper, n_pages, source, words, 8.0, 8.0, 0.0, 0.0, 8.0, 8.0,
                         SAFE, False, None, {"w": AUDIO_PX[0], "h": AUDIO_PX[1]})
    spine = spine_width(n_pages, paper)
    bleed = BLEED
    if fmt == "hardcover":
        bleed = HARDCOVER_WRAP  # approximation: KDP's case-wrap template also adds hinge space
    wrap_w = round(2 * tw + spine + 2 * bleed, 4)
    wrap_h = round(th + 2 * bleed, 4)
    barcode = {
        "x_in": round(bleed + tw - TEXT_MARGIN - BARCODE_W, 4),
        "y_in": round(bleed + th - TEXT_MARGIN - BARCODE_H, 4),
        "w_in": BARCODE_W,
        "h_in": BARCODE_H,
    }
    return CoverSpec(fmt, trim, paper, n_pages, source, words, tw, th, bleed, spine, wrap_w, wrap_h,
                     SAFE, n_pages >= SPINE_TEXT_MIN_PAGES, barcode, None)


def back_copy_budget(spec: CoverSpec) -> int:
    """Characters of back copy that fit in the back panel above the barcode keep-out."""
    if spec.format in ("ebook", "audiobook"):
        return 0
    w = spec.trim_w_in - 2 * TEXT_MARGIN
    h = spec.trim_h_in - 2 * TEXT_MARGIN - BARCODE_H - 0.25
    return max(0, int(w * h * CHARS_PER_SQ_IN))


def image_dpi(width_px: int, height_px: int, spec: CoverSpec) -> float:
    """Effective dpi of a front image stretched over the front panel plus its bleed."""
    panel_w = spec.trim_w_in + spec.bleed_in
    panel_h = spec.trim_h_in + 2 * spec.bleed_in
    if not width_px or not height_px:
        return 0.0
    return round(min(width_px / panel_w, height_px / panel_h), 1)


def preflight(spec: CoverSpec, *, title: str, back_copy: str, spine_text: str,
              image: Optional[dict]) -> list[dict]:
    """[{key, label, status: pass|warn|fail, detail}]"""
    out: list[dict] = []

    def add(key: str, label: str, status: str, detail: str) -> None:
        out.append({"key": key, "label": label, "status": status, "detail": detail})

    add("title", "Title present", "pass" if (title or "").strip() else "fail",
        "Title set" if (title or "").strip() else "Give the book a title")

    if not image:
        add("front_image", "Front image", "fail", "Choose or upload a front image")
    elif image.get("content_type") == "image/svg+xml":
        add("front_image", "Front image", "pass", "Vector art scales to any size")
    elif spec.pixels:
        need_w, need_h = spec.pixels["w"], spec.pixels["h"]
        w, h = image.get("width", 0), image.get("height", 0)
        ok = w >= need_w and h >= need_h
        add("front_image", "Front image size", "pass" if ok else "warn",
            f"{w}x{h} px" + ("" if ok else f", stores want {need_w}x{need_h} px"))
    else:
        dpi = image_dpi(image.get("width", 0), image.get("height", 0), spec)
        status = "pass" if dpi >= 300 else ("warn" if dpi >= 200 else "fail")
        add("front_image", "Front image 300 dpi", status,
            f"{dpi:.0f} dpi at {spec.trim}" + ("" if dpi >= 300 else ", below 300 dpi print minimum"))

    if spec.format in ("paperback", "hardcover"):
        budget = back_copy_budget(spec)
        n = len((back_copy or "").strip())
        if n == 0:
            add("back_copy", "Back copy", "warn", "No back copy yet")
        else:
            add("back_copy", "Back copy fits safe area", "pass" if n <= budget else "fail",
                f"{n} of about {budget} characters")
        if spine_text.strip():
            if spec.spine_text_allowed:
                add("spine_text", "Spine text", "pass", f"{spec.pages} pages, {spec.spine_in:.3f} in spine")
            else:
                add("spine_text", "Spine text", "fail",
                    f"KDP allows spine text from {SPINE_TEXT_MIN_PAGES} pages; this book has {spec.pages}")
        else:
            add("spine_text", "Spine text", "pass" if not spec.spine_text_allowed else "warn",
                "Blank spine" if not spec.spine_text_allowed else "Spine is wide enough for a title")
        add("barcode", "Barcode area clear", "pass", f"{BARCODE_W} x {BARCODE_H} in keep-out reserved")
    return out


# ------------------------------------------------------------------ export

def _hex(color: str, default: str) -> str:
    c = (color or default).strip()
    return c if c.startswith("#") and len(c) in (4, 7) else default


def render_wrap_pdf(spec: CoverSpec, *, title: str, author: str, back_copy: str, spine_text: str,
                    image_path: Optional[str], colors: dict) -> bytes:
    """Print-ready full wrap with reportlab. Raises ImportError if reportlab is missing."""
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Frame, Paragraph

    pt = 72.0
    W, H = spec.wrap_w_in * pt, spec.wrap_h_in * pt
    bg = HexColor(_hex(colors.get("background", ""), "#14131a"))
    fg = HexColor(_hex(colors.get("text", ""), "#ffffff"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"{title} cover wrap")
    c.setFillColor(bg)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    b = spec.bleed_in * pt
    tw = spec.trim_w_in * pt
    sp = spec.spine_in * pt
    front_x = b + tw + sp

    if image_path:
        try:
            c.drawImage(image_path, front_x, 0, width=W - front_x, height=H,
                        preserveAspectRatio=False, mask="auto")
        except Exception:  # noqa: BLE001 - unsupported image (e.g. SVG): leave the colour field
            pass
    else:
        c.setFillColor(fg)
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(front_x + tw / 2, H * 0.62, title[:40])
        c.setFont("Helvetica", 16)
        c.drawCentredString(front_x + tw / 2, H * 0.2, author[:50])

    # Back copy
    m = TEXT_MARGIN * pt
    style = ParagraphStyle("back", fontName="Times-Roman", fontSize=11, leading=15, textColor=fg)
    frame = Frame(b + m, b + m + (BARCODE_H + 0.25) * pt, tw - 2 * m,
                  spec.trim_h_in * pt - 2 * m - (BARCODE_H + 0.25) * pt, showBoundary=0)
    paras = [Paragraph(p.replace("&", "&amp;").replace("<", "&lt;"), style)
             for p in (back_copy or "").split("\n\n") if p.strip()]
    frame.addFromList(paras, c)

    # Barcode keep-out (white box, bottom right of back panel)
    bc = spec.barcode_box or {}
    if bc:
        c.setFillColor(white)
        c.rect(bc["x_in"] * pt, H - (bc["y_in"] + bc["h_in"]) * pt, bc["w_in"] * pt, bc["h_in"] * pt,
               stroke=0, fill=1)

    # Spine text, rotated to read top-to-bottom
    if spine_text.strip() and spec.spine_text_allowed:
        c.saveState()
        c.translate(b + tw + sp / 2, H / 2)
        c.rotate(-90)
        c.setFillColor(fg)
        size = max(6.0, min(14.0, sp * 0.55))
        c.setFont("Helvetica-Bold", size)
        c.drawCentredString(0, -size / 3, spine_text[:60])
        c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()


def render_ebook_jpeg(*, title: str, author: str, image_bytes: Optional[bytes], colors: dict,
                      size: tuple[int, int] = EBOOK_PX) -> bytes:
    """Front cover as a store-ready JPEG (cover-fit crop). Raises ImportError without Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = size
    canvas_img: Image.Image
    if image_bytes:
        try:
            src = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            scale = max(W / src.width, H / src.height)
            resized = src.resize((math.ceil(src.width * scale), math.ceil(src.height * scale)),
                                 Image.LANCZOS)
            left = (resized.width - W) // 2
            top = (resized.height - H) // 2
            canvas_img = resized.crop((left, top, left + W, top + H))
        except Exception:  # noqa: BLE001
            image_bytes = None
    if not image_bytes:
        canvas_img = Image.new("RGB", (W, H), _hex(colors.get("background", ""), "#14131a"))
        d = ImageDraw.Draw(canvas_img)
        try:
            big = ImageFont.load_default(size=int(W * 0.08))
            small = ImageFont.load_default(size=int(W * 0.04))
        except TypeError:  # pragma: no cover - old Pillow
            big = small = ImageFont.load_default()
        fg = _hex(colors.get("text", ""), "#ffffff")
        d.text((W / 2, H * 0.4), title[:40], fill=fg, font=big, anchor="mm")
        d.text((W / 2, H * 0.85), author[:50], fill=fg, font=small, anchor="mm")
    out = io.BytesIO()
    canvas_img.save(out, "JPEG", quality=90, optimize=True)
    return out.getvalue()
