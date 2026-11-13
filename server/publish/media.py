"""Media library storage: sha256-deduped files under settings().media_dir/<project>/."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..models import CodexEntry, CoverDesign, Media

MAX_BYTES = 15 * 1024 * 1024
KINDS = ("image", "cover", "portrait", "map", "reference")

EXT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "svg": "image/svg+xml",
}
TYPE_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp",
            "image/gif": "gif", "image/svg+xml": "svg"}


class MediaError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _sniff(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:2048].lstrip().lower()
    if head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head:
        return "image/svg+xml"
    return None


def detect_type(data: bytes, filename: str = "", declared: str = "") -> str:
    """Trust the bytes first; fall back to extension/declared type only for SVG text."""
    sniffed = _sniff(data)
    if sniffed:
        return sniffed
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    declared = (declared or "").split(";")[0].strip().lower()
    if ext == "svg" or declared == "image/svg+xml":
        return "image/svg+xml"
    raise MediaError(415, "Only png, jpg, webp, gif and svg images are accepted.")


def _dimensions(data: bytes, ctype: str) -> tuple[int, int]:
    if ctype == "image/svg+xml":
        text = data[:4096].decode("utf-8", "ignore")
        w = re.search(r'\bwidth="([\d.]+)', text)
        h = re.search(r'\bheight="([\d.]+)', text)
        if w and h:
            return int(float(w.group(1))), int(float(h.group(1)))
        vb = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)', text)
        if vb:
            return int(float(vb.group(1))), int(float(vb.group(2)))
        return 0, 0
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return 0, 0
    try:
        with Image.open(io.BytesIO(data)) as im:
            return int(im.width), int(im.height)
    except Exception:  # noqa: BLE001
        raise MediaError(415, "That file is not a readable image.")


def project_dir(project_id: str) -> Path:
    d = settings().media_dir / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_path(m: Media) -> Path:
    ext = TYPE_EXT.get(m.content_type, "bin")
    return settings().media_dir / m.project_id / f"{m.sha256}.{ext}"


def store(session: Session, project_id: str, data: bytes, *, filename: str = "", declared: str = "",
          source: str = "upload", kind: str = "image") -> tuple[Media, bool]:
    """Save bytes as Media. Returns (row, created). Same bytes in the same project dedupe."""
    if not data:
        raise MediaError(400, "Empty file.")
    if len(data) > MAX_BYTES:
        raise MediaError(413, "Images are limited to 15 MB each.")
    ctype = detect_type(data, filename, declared)
    sha = hashlib.sha256(data).hexdigest()
    existing = session.exec(
        select(Media).where(Media.project_id == project_id, Media.sha256 == sha)
    ).first()
    if existing:
        return existing, False
    width, height = _dimensions(data, ctype)
    m = Media(project_id=project_id, filename=(filename or f"image.{TYPE_EXT[ctype]}")[:255],
              content_type=ctype, sha256=sha, size=len(data), width=width, height=height,
              kind=kind if kind in KINDS else "image", source=source)
    project_dir(project_id)
    path = file_path(m)
    if not path.exists():
        path.write_bytes(data)
    session.add(m)
    session.commit()
    session.refresh(m)
    return m, True


def remove(session: Session, m: Media) -> None:
    """Delete a row and its file, clearing references first (FKs are enforced)."""
    for c in session.exec(select(CoverDesign).where(CoverDesign.front_media_id == m.id)).all():
        c.front_media_id = None
        session.add(c)
    for e in session.exec(select(CodexEntry).where(CodexEntry.image_media_id == m.id)).all():
        e.image_media_id = None
        session.add(e)
    path = file_path(m)
    session.delete(m)
    session.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - file locked on Windows
        pass


def fetch_url(url: str) -> tuple[bytes, str, str]:
    """Download an image with a hard 15 MB cap. Returns (data, content_type, filename)."""
    import httpx

    if not re.match(r"^https?://", url or "", re.I):
        raise MediaError(400, "Use an http(s) URL.")
    try:
        with httpx.Client(follow_redirects=True, timeout=20.0,
                          headers={"User-Agent": "NovelOS-media-import/2"}) as c:
            with c.stream("GET", url) as r:
                if r.status_code >= 400:
                    raise MediaError(400, f"The server answered {r.status_code}.")
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if not ctype.startswith("image/") or ctype not in TYPE_EXT:
                    raise MediaError(415, "That URL is not a png, jpg, webp, gif or svg image.")
                declared_len = int(r.headers.get("content-length") or 0)
                if declared_len > MAX_BYTES:
                    raise MediaError(413, "Images are limited to 15 MB each.")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        raise MediaError(413, "Images are limited to 15 MB each.")
    except httpx.HTTPError as e:
        raise MediaError(400, f"Could not fetch that URL: {e}")
    name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or f"import.{TYPE_EXT[ctype]}"
    return bytes(buf), ctype, name
