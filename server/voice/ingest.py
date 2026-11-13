"""Turn uploaded files into plain sample text."""

from __future__ import annotations

import io

from core.prose_sanitize import extract_html_comments, strip_state_blocks

ALLOWED = (".txt", ".md", ".docx")


def docx_available() -> bool:
    try:
        import docx  # noqa: F401
    except ImportError:
        return False
    return True


def read_upload(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if not name.endswith(ALLOWED):
        raise ValueError("Upload a .txt, .md or .docx file.")
    if name.endswith(".docx"):
        if not docx_available():
            raise ValueError("Install python-docx to read .docx files.")
        import docx
        doc = docx.Document(io.BytesIO(data))
        text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        text = data.decode("utf-8-sig", errors="replace")
    return clean(text)


def clean(text: str) -> str:
    """Strip HTML comments / state blocks; keep the author's punctuation intact."""
    body, _meta = extract_html_comments(text or "")
    return strip_state_blocks(body).strip()
