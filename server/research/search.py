"""Web search, pluggable: Tavily or Brave when a key is set, else DuckDuckGo HTML (no key)."""

from __future__ import annotations

import os
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .browser import TIMEOUT, USER_AGENT

__all__ = ["search", "provider_name", "parse_ddg"]


def provider_name() -> str:
    if os.environ.get("TAVILY_API_KEY"):
        return "tavily"
    if os.environ.get("BRAVE_API_KEY"):
        return "brave"
    return "duckduckgo"


class _DDG(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[dict] = []
        self.mode = ""  # title | snippet

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "a" and "result__a" in cls:
            self.results.append({"title": "", "url": _ddg_target(a.get("href") or ""), "snippet": ""})
            self.mode = "title"
        elif "result__snippet" in cls and self.results:
            self.mode = "snippet"

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("a", "td", "div") and self.mode:
            self.mode = ""

    def handle_data(self, data):  # noqa: ANN001
        if self.mode and self.results:
            self.results[-1][self.mode] += data


def _ddg_target(href: str) -> str:
    """DuckDuckGo wraps results as //duckduckgo.com/l/?uddg=<url>."""
    if href.startswith("//"):
        href = "https:" + href
    q = parse_qs(urlparse(href).query)
    return unquote(q["uddg"][0]) if "uddg" in q else href


def parse_ddg(html: str) -> list[dict]:
    p = _DDG()
    p.feed(html)
    out = []
    for r in p.results:
        url = r["url"]
        if not url.startswith("http") or "duckduckgo.com/y.js" in url:
            continue  # ads
        out.append({"title": " ".join(r["title"].split()), "url": url, "snippet": " ".join(r["snippet"].split())})
    return out


def _duckduckgo(query: str, n: int) -> list[dict]:
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query},
                   headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)
    r.raise_for_status()
    return parse_ddg(r.text)[:n]


def _brave(query: str, n: int) -> list[dict]:
    r = httpx.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": n},
                  headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"], "Accept": "application/json"},
                  timeout=TIMEOUT)
    r.raise_for_status()
    hits = (r.json().get("web") or {}).get("results") or []
    return [{"title": h.get("title", ""), "url": h.get("url", ""), "snippet": h.get("description", "")}
            for h in hits][:n]


def _tavily(query: str, n: int) -> list[dict]:
    r = httpx.post("https://api.tavily.com/search",
                   json={"api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": n},
                   timeout=TIMEOUT * 2)
    r.raise_for_status()
    return [{"title": h.get("title", ""), "url": h.get("url", ""), "snippet": (h.get("content") or "")[:300]}
            for h in r.json().get("results") or []][:n]


def search(query: str, n: int = 5) -> list[dict]:
    """Top N results as [{title, url, snippet}]."""
    fn = {"tavily": _tavily, "brave": _brave, "duckduckgo": _duckduckgo}[provider_name()]
    return [h for h in fn(query, n) if h.get("url")]
