"""Browser agent: fetch a URL and return readable text.

Two backends behind one interface, ``fetch(url) -> Page``:

* ``http``: httpx plus a stdlib ``html.parser`` extractor (always available).
* ``playwright``: headless Chromium for JS-heavy pages, used automatically when
  installed (``pip install playwright && playwright install chromium``), with a
  fallback to ``http`` if it fails to launch.

Fetching is polite: honest User-Agent, robots.txt, 10s timeout, 2 MB cap and at
most one request in flight per domain.
"""

from __future__ import annotations

import atexit
import importlib.util
import os
import threading
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "NovelOS-Research/2.0 (+https://github.com/mrigankad/Novel-OS)"
TIMEOUT = 10.0
MAX_BYTES = 2 * 1024 * 1024
MAX_CHARS = 20_000

__all__ = ["Page", "FetchError", "RobotsDisallowed", "fetch", "extract", "allowed", "backend_name"]


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


@dataclass
class Page:
    url: str
    title: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ extraction

_SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg",
         "iframe", "template", "button", "select"}
_BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "td", "th",
          "dd", "dt", "figcaption", "article", "section", "div", "br", "tr"}
_VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed"}


class _Extractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.skip_depth = 0
        self.in_title = False
        self.title = ""
        self.blocks: list[str] = []
        self.buf: list[str] = []
        self.heading = False
        self.links: list[str] = []

    def _flush(self) -> None:
        text = " ".join("".join(self.buf).split())
        if text:
            self.blocks.append(("## " + text) if self.heading else text)
        self.buf = []
        self.heading = False

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in _SKIP:
            if tag not in _VOID:
                self.skip_depth += 1
            return
        if tag == "title":
            self.in_title = True
        if self.skip_depth:
            return
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self.links.append(urljoin(self.base, href))
        if tag in _BLOCK:
            self._flush()
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                self.heading = True

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in _SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "title":
            self.in_title = False
        if not self.skip_depth and tag in _BLOCK:
            self._flush()

    def handle_data(self, data):  # noqa: ANN001
        if self.in_title:
            self.title += data
            return
        if not self.skip_depth:
            self.buf.append(data)


def extract(html: str, url: str = "") -> Page:
    """Strip chrome (nav, scripts, styles), keep headings and paragraphs, cap the text."""
    p = _Extractor(url)
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - malformed HTML still yields what we parsed
        pass
    p._flush()
    text = "\n\n".join(p.blocks)[:MAX_CHARS]
    seen: set[str] = set()
    links = [u for u in p.links if u.startswith("http") and not (u in seen or seen.add(u))]
    return Page(url=url, title=" ".join(p.title.split()), text=text, links=links[:200])


# ------------------------------------------------------------------ politeness

_robots: dict[str, RobotFileParser | None] = {}
_robots_lock = threading.Lock()
_domain_locks: dict[str, threading.Lock] = {}
_domain_guard = threading.Lock()


def _domain_lock(host: str) -> threading.Lock:
    with _domain_guard:
        return _domain_locks.setdefault(host, threading.Lock())


def _load_robots(origin: str) -> RobotFileParser | None:
    rp = RobotFileParser()
    try:
        r = httpx.get(origin + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
                      follow_redirects=True)
    except httpx.HTTPError:
        return None  # unreachable robots.txt: treat as allowed
    if r.status_code in (401, 403):
        rp.disallow_all = True
    elif r.status_code >= 400:
        rp.allow_all = True
    else:
        rp.parse(r.text.splitlines())
    return rp


def allowed(url: str) -> bool:
    """robots.txt check, cached per origin."""
    u = urlparse(url)
    origin = f"{u.scheme}://{u.netloc}"
    with _robots_lock:
        cached = origin in _robots
        rp = _robots.get(origin)
    if not cached:
        rp = _load_robots(origin)
        with _robots_lock:
            _robots[origin] = rp
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def clear_cache() -> None:
    with _robots_lock:
        _robots.clear()


# ------------------------------------------------------------------ backends

def _playwright_available() -> bool:
    if os.environ.get("NOVEL_OS_RESEARCH_BROWSER", "").lower() == "http":
        return False
    return importlib.util.find_spec("playwright") is not None


def backend_name() -> str:
    return "playwright" if _playwright_available() else "http"


def _fetch_http(url: str) -> Page:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers=headers) as c:
        with c.stream("GET", url) as r:
            if r.status_code >= 400:
                raise FetchError(f"HTTP {r.status_code} for {url}")
            ctype = r.headers.get("content-type", "")
            if ctype and "html" not in ctype and "text" not in ctype:
                raise FetchError(f"Not a web page ({ctype})")
            if int(r.headers.get("content-length") or 0) > MAX_BYTES:
                raise FetchError("Page larger than 2 MB")
            chunks, size = [], 0
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    break  # keep what we have
                chunks.append(chunk)
            body = b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")
            final = str(r.url)
    return extract(body, final)


_pw_local = threading.local()
_pw_all: list = []  # (playwright, browser) pairs, closed at exit
_pw_all_lock = threading.Lock()


def _shared_browser():
    """One headless Chromium per worker thread, reused across pages.

    Launching Chromium costs ~1-2s; a fresh *context* per page costs ~50ms and
    still isolates cookies/storage. Playwright's sync objects are thread-bound,
    hence thread-local rather than one global browser."""
    b = getattr(_pw_local, "browser", None)
    if b is not None and b.is_connected():
        return b
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]

    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    _pw_local.pw, _pw_local.browser = pw, b
    with _pw_all_lock:
        _pw_all.append((pw, b))
    return b


def _close_browsers() -> None:
    with _pw_all_lock:
        pairs, _pw_all[:] = list(_pw_all), []
    for pw, b in pairs:
        for closer in (b.close, pw.stop):
            try:
                closer()
            except Exception:  # noqa: BLE001 - best effort at shutdown
                pass


atexit.register(_close_browsers)


def _fetch_playwright(url: str) -> Page:
    browser = _shared_browser()
    ctx = browser.new_context(user_agent=USER_AGENT)
    try:
        page = ctx.new_page()
        resp = page.goto(url, timeout=TIMEOUT * 1000, wait_until="domcontentloaded")
        if resp and resp.status >= 400:
            raise FetchError(f"HTTP {resp.status} for {url}")
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:  # noqa: BLE001 - busy pages never go idle; use what rendered
            pass
        html = page.content()[:MAX_BYTES]
        return extract(html, page.url)
    finally:
        ctx.close()


def fetch(url: str) -> Page:
    """Fetch and extract one page. Raises RobotsDisallowed / FetchError."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise FetchError(f"Unsupported URL: {url}")
    if not allowed(url):
        raise RobotsDisallowed(f"robots.txt disallows {url}")
    with _domain_lock(u.netloc.lower()):
        if _playwright_available():
            try:
                return _fetch_playwright(url)
            except FetchError:
                raise
            except Exception:  # noqa: BLE001 - chromium missing or crashed: fall back
                pass
        try:
            return _fetch_http(url)
        except httpx.HTTPError as e:
            raise FetchError(f"{type(e).__name__}: {e}") from e
