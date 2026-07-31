"""Media storage content-addressed image blobs.

Backs Codex portraits, the research moodboard, and inline manuscript images
(PLAN.md P0.3). Dev writes to the local filesystem; production swaps in an
S3-compatible store behind the same `MediaStore` interface.

Two properties matter:

* **Content-addressed.** A blob's path is the SHA-256 of its bytes, so
  re-uploading the same image de-duplicates for free and served URLs are
  immutably cacheable.
* **The user's filename never touches the path.** It is metadata only. That
  removes path traversal as a category of bug rather than filtering for it.

Blobs are namespaced per project so a tenant boundary can be drawn around a
directory later (P0.5).
"""

from __future__ import annotations

import hashlib
import re
import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

# SVG is deliberately absent: it can carry script and would execute if served
# inline. If vector art is needed later it must be sanitised first.
ALLOWED_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}

MAX_BYTES = 10 * 1024 * 1024  # 10 MiB

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]")


class MediaError(ValueError):
    """Upload rejected. Carries an HTTP status for the route layer."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_filename(name: str) -> str:
    """Keep a readable label for the UI. Never used to build a path."""
    base = Path(name or "").name
    cleaned = _SAFE_NAME.sub("_", base).strip() or "image"
    return cleaned[:120]


def validate(data: bytes, content_type: str) -> str:
    """Check size and type. Returns the extension for the stored blob."""
    ext = ALLOWED_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if ext is None:
        raise MediaError(
            f"Unsupported image type {content_type!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
            status=415,
        )
    if not data:
        raise MediaError("Empty upload.")
    if len(data) > MAX_BYTES:
        raise MediaError(f"Image exceeds the {MAX_BYTES // (1024 * 1024)} MiB limit.", status=413)
    return ext


# --------------------------------------------------------------------- dimensions

def dimensions(data: bytes) -> tuple[int, int]:
    """Best-effort intrinsic size, parsed from the file header.

    Used so the editor can reserve space and avoid layout shift. Reading a few
    header bytes keeps Pillow out of the dependency list; an unrecognised or
    truncated header simply yields (0, 0) and the caller lays out fluidly.
    """
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            w, h = struct.unpack(">II", data[16:24])
            return int(w), int(h)

        if data[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", data[6:10])
            return int(w), int(h)

        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return _webp_dimensions(data)

        if data[:2] == b"\xff\xd8":
            return _jpeg_dimensions(data)
    except (struct.error, IndexError, ValueError):
        pass
    return 0, 0


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    fourcc = data[12:16]
    if fourcc == b"VP8X":
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return w, h
    if fourcc == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if fourcc == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return 0, 0


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0-SOF15, excluding the non-frame markers DHT/JPG/DAC.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return int(w), int(h)
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return 0, 0


# ------------------------------------------------------------------------ stores

class MediaStore(ABC):
    """Blob persistence. Metadata lives in the database, bytes live here."""

    @abstractmethod
    def put(self, project_id: str, sha: str, ext: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, project_id: str, sha: str, ext: str) -> Optional[bytes]: ...

    @abstractmethod
    def delete(self, project_id: str, sha: str, ext: str) -> bool: ...


class LocalMediaStore(MediaStore):
    """Filesystem store: <root>/<project>/<sha[:2]>/<sha><ext>."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, project_id: str, sha: str, ext: str) -> Path:
        # Both components are validated: project ids are slugs and sha is hex,
        # so neither can escape the root.
        if not re.fullmatch(r"[A-Za-z0-9._-]+", project_id or ""):
            raise MediaError("Invalid project id.", status=404)
        if not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
            raise MediaError("Invalid media digest.", status=404)
        return self.root / project_id / sha[:2] / f"{sha}{ext}"

    def put(self, project_id: str, sha: str, ext: str, data: bytes) -> None:
        path = self._path(project_id, sha, ext)
        if path.exists():
            return  # content-addressed: identical bytes, nothing to rewrite
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: write beside the target, then rename into place.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def read(self, project_id: str, sha: str, ext: str) -> Optional[bytes]:
        path = self._path(project_id, sha, ext)
        return path.read_bytes() if path.exists() else None

    def delete(self, project_id: str, sha: str, ext: str) -> bool:
        path = self._path(project_id, sha, ext)
        if not path.exists():
            return False
        path.unlink()
        return True
