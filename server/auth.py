"""Studio access control.

Novel OS is a single-author studio. Two modes:

* No NOVEL_OS_PASSWORD (default): the studio only answers requests that come
  from this computer. Beta-reader links (/api/read/...) work from anywhere.
* NOVEL_OS_LOCAL_ONLY=0 (no password): answer any device. Only for a trusted
  private network or Docker on your own machine; anyone who can reach it can
  use the studio.
* NOVEL_OS_PASSWORD set: any device may use the studio after signing in; the
  session is an HttpOnly, HMAC-signed cookie. Reader links stay public.

Requests arrive through the Next.js proxy, so the original client address is
taken from X-Forwarded-For when the direct peer is loopback (the proxy).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from typing import Optional

from .config import settings

COOKIE = "novelos_session"
SESSION_DAYS = 30
# Always public: reader links, health, and signing in.
PUBLIC_PREFIXES = ("/api/read/", "/api/health", "/api/auth/")


def password() -> str:
    return os.environ.get("NOVEL_OS_PASSWORD", "")


def _secret() -> bytes:
    """Signing key: NOVEL_OS_SECRET, else a random key persisted in the data dir."""
    env = os.environ.get("NOVEL_OS_SECRET")
    if env:
        return env.encode()
    path = settings().data_dir / ".session_secret"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


def issue() -> str:
    expires = int(time.time()) + SESSION_DAYS * 86400
    body = f"v1.{expires}"
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def valid(token: Optional[str]) -> bool:
    if not token or token.count(".") != 2:
        return False
    version, expires, sig = token.split(".")
    body = f"{version}.{expires}"
    good = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and expires.isdigit() and int(expires) > time.time()


def check_password(given: str) -> bool:
    pw = password()
    return bool(pw) and hmac.compare_digest(given.encode(), pw.encode())


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host.strip().strip("[]")).is_loopback
    except ValueError:
        return host.strip().lower() == "localhost"


def client_is_local(peer: Optional[str], forwarded_for: Optional[str]) -> bool:
    """True when the real client is this computer. Behind the Next proxy the peer
    is loopback, so the first X-Forwarded-For hop decides."""
    if not peer or not _is_loopback(peer):
        return False
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        return _is_loopback(first)
    return True


def is_public(path: str) -> bool:
    return path.startswith(PUBLIC_PREFIXES) or path == "/api/health"


def allowed(path: str, peer: Optional[str], forwarded_for: Optional[str], cookie: Optional[str]) -> tuple[bool, int, str]:
    """(ok, status, message) for one request."""
    if not path.startswith("/api/") or is_public(path):
        return True, 200, ""
    if password():
        if valid(cookie):
            return True, 200, ""
        return False, 401, "Sign in to use this studio."
    if client_is_local(peer, forwarded_for) or os.environ.get("NOVEL_OS_LOCAL_ONLY", "1") == "0":
        return True, 200, ""
    return False, 403, ("This studio only answers this computer. Set NOVEL_OS_PASSWORD on the server "
                        "to use it from other devices.")
