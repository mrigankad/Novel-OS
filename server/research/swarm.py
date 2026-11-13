"""Swarm orchestration: plan sub-queries, run parallel browser workers, synthesize.

    task = swarm.create(session, project, question, chapter)
    swarm.submit(task)               # background job (or synchronous when SYNC)

Pipeline (each step updates ResearchTask.progress and publishes research.updated):
  1. plan       LLM splits the question into 2-4 sub-queries using project context
  2. search     up to 4 workers search in parallel; URLs are deduped
  3. read       workers fetch 2-3 pages each and extract findings as JSON
  4. synthesize dedupe findings, write a cited summary in our own words
  5. remember   strong findings become shared project memories (kind="research")

Copyright: excerpts are verbatim quotes of at most 300 characters; summaries and
notes are paraphrase.
"""

from __future__ import annotations

import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import urlparse

from sqlmodel import Session, select

from .. import events, jobs, llm
from ..db import engine, session_scope
from ..models import Memory, Project, ResearchSource, ResearchTask
from ..models.base import now
from . import browser
from . import search as search_mod

MAX_WORKERS = 4
PAGES_PER_QUERY = 3
RESULTS_PER_QUERY = 5
EXCERPT_MAX = 300
MEMORY_THRESHOLD = 0.6
PAGE_CHARS_FOR_LLM = 12_000

# Tests (or NOVEL_OS_JOBS_INLINE=1) run the pipeline synchronously in the request.
SYNC = os.environ.get("NOVEL_OS_JOBS_INLINE") == "1"

_write_lock = threading.Lock()
_active: dict[str, int] = {}  # task_id -> live worker count


class Cancelled(Exception):
    pass


# ------------------------------------------------------------------ helpers

def domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _norm(s: str) -> str:
    return " ".join(s.split())


def cap_excerpt(text: str, limit: int = EXCERPT_MAX) -> str:
    """Keep a quote verbatim but no longer than `limit` chars, cut at a word boundary."""
    t = _norm(text)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    if " " in cut[limit // 2:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:")


def parse_json(text: str, want: type = list):
    """Pull the first JSON array/object out of a model reply (tolerates prose and fences)."""
    text = re.sub(r"```(?:json)?", "", text or "")
    opener, closer = ("[", "]") if want is list else ("{", "}")
    start = text.find(opener)
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        val = json.loads(text[start:i + 1])
                        if isinstance(val, want):
                            return val
                    except json.JSONDecodeError:
                        break
                    break
        start = text.find(opener, start + 1)
    return want()


def _ask(system: str, user: str, max_tokens: int = 1500) -> str:
    with Session(engine()) as s:
        text, _route, _model = llm.complete(s, system, user, max_tokens=max_tokens)
    return text or ""


def _update(task_id: str, project_id: str, **fields) -> None:
    with _write_lock, session_scope() as s:
        t = s.get(ResearchTask, task_id)
        if not t:
            raise Cancelled()
        if t.status == "cancelled" and fields.get("status") not in ("cancelled",):
            raise Cancelled()
        for k, v in fields.items():
            setattr(t, k, v)
        s.add(t)
        status = t.status
    events.publish(project_id, "research.updated", {"id": task_id, "status": status,
                                                    "progress": fields.get("progress", "")})


def _check(task_id: str) -> None:
    with Session(engine()) as s:
        t = s.get(ResearchTask, task_id)
        if not t or t.status == "cancelled":
            raise Cancelled()


def project_context(p: Project) -> str:
    bible = p.bible or {}
    era = bible.get("era") or bible.get("period") or bible.get("time_period") or ""
    setting = bible.get("setting") or ""
    if isinstance(setting, dict):
        setting = ", ".join(f"{k}: {v}" for k, v in setting.items())
    lines = [f"Title: {p.title}"]
    for label, val in (("Genre", p.genre), ("Premise", p.premise), ("Era", era), ("Setting", setting)):
        if val:
            lines.append(f"{label}: {val}")
    return "\n".join(lines)


# ------------------------------------------------------------------ steps

PLAN_SYSTEM = (
    "You plan web research for a novelist. Split the question into 2 to 4 focused web search queries "
    "that together answer it. Use the book's context (era, place, genre) to make queries specific. "
    'Reply with JSON only: ["query one", "query two"]'
)

EXTRACT_SYSTEM = (
    "You extract research findings from a web page for a novelist. Return JSON only: "
    '[{"claim": "...", "excerpt": "...", "url": "...", "reliability": 0.0}]. '
    "claim: one fact, in your own words. excerpt: a VERBATIM quote from the page that supports it, "
    "at most 300 characters. reliability: 0 to 1 (primary sources, museums, universities and archives "
    "score high; forums and content farms low). Give at most 5 findings; return [] if the page is irrelevant."
)

SYNTH_SYSTEM = (
    "You write research briefs for a novelist. Using only the numbered findings, answer the question in "
    "2 to 4 short paragraphs, in your own words (never copy the excerpts). Cite findings inline like [1] or "
    "[2][3]. Note disagreements between sources and end with one line on what a scene could use."
)


def plan(question: str, context: str) -> list[str]:
    reply = _ask(PLAN_SYSTEM, f"Book context:\n{context}\n\nQuestion: {question}", 400)
    subs = [q.strip() for q in parse_json(reply, list) if isinstance(q, str) and q.strip()]
    if not subs:
        subs = [question]
    return subs[:4]


def extract_findings(question: str, sub: str, page: browser.Page) -> list[dict]:
    user = (f"Research question: {question}\nSub-query: {sub}\nURL: {page.url}\nTitle: {page.title}\n\n"
            f"Page text:\n{page.text[:PAGE_CHARS_FOR_LLM]}")
    raw = parse_json(_ask(EXTRACT_SYSTEM, user, 1200), list)
    page_norm = _norm(page.text).lower()
    out = []
    for f in raw:
        if not isinstance(f, dict) or not str(f.get("claim", "")).strip():
            continue
        excerpt = cap_excerpt(str(f.get("excerpt", "")))
        if excerpt and excerpt.lower() not in page_norm:
            continue  # not a verbatim quote: drop rather than misattribute
        try:
            rel = max(0.0, min(1.0, float(f.get("reliability", 0.5))))
        except (TypeError, ValueError):
            rel = 0.5
        out.append({"claim": _norm(str(f["claim"]))[:600], "excerpt": excerpt, "url": page.url,
                    "title": page.title or domain(page.url), "reliability": rel})
    return out


def dedupe(findings: list[dict]) -> list[dict]:
    """Same claim from several pages: keep the most reliable copy."""
    best: dict[str, dict] = {}
    for f in findings:
        key = " ".join(re.sub(r"[^a-z0-9 ]", " ", f["claim"].lower()).split())[:90]
        if key not in best or f["reliability"] > best[key]["reliability"]:
            best[key] = f
    return sorted(best.values(), key=lambda f: -f["reliability"])


def synthesize(question: str, context: str, findings: list[dict]) -> str:
    if not findings:
        return "The browsers found no usable sources for this question. Try rephrasing it or narrowing the era or place."
    numbered = "\n".join(f"[{i}] {f['claim']} ({domain(f['url'])}, reliability {f['reliability']:.1f})"
                         for i, f in enumerate(findings, 1))
    return _ask(SYNTH_SYSTEM, f"Book context:\n{context}\n\nQuestion: {question}\n\nFindings:\n{numbered}", 1500).strip()


# ------------------------------------------------------------------ the job

def run_task(task_id: str) -> dict:
    with Session(engine()) as s:
        task = s.get(ResearchTask, task_id)
        if not task:
            return {}
        project = s.get(Project, task.project_id)
        question, chapter, pid = task.question, task.chapter, task.project_id
        context = project_context(project) if project else ""
    try:
        return _pipeline(task_id, pid, question, chapter, context)
    except Cancelled:
        return {"cancelled": True}
    except Exception as e:
        try:
            _update(task_id, pid, status="failed", progress=f"Failed: {e}"[:300], finished_at=now())
        except Cancelled:
            pass
        raise
    finally:
        _active.pop(task_id, None)


def _pipeline(task_id: str, pid: str, question: str, chapter: Optional[int], context: str) -> dict:
    _update(task_id, pid, status="browsing", progress="Planning the search")
    subs = plan(question, context)
    _update(task_id, pid, progress=f"Searching {len(subs)} angles: " + "; ".join(subs)[:220])

    workers = min(MAX_WORKERS, len(subs))
    _active[task_id] = workers

    def do_search(q: str) -> list[dict]:
        try:
            return search_mod.search(q, RESULTS_PER_QUERY)
        except Exception:  # noqa: BLE001 - one dead search shouldn't sink the swarm
            return []

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research-search") as pool:
        results = list(pool.map(do_search, subs))

    seen: set[str] = set()
    plan_pages: list[tuple[str, str]] = []  # (sub-query, url)
    for q, hits in zip(subs, results):
        taken = 0
        for h in hits:
            url = h.get("url", "")
            if url in seen or taken >= PAGES_PER_QUERY:
                continue
            seen.add(url)
            plan_pages.append((q, url))
            taken += 1
    _check(task_id)

    total = len(plan_pages)
    counter = {"n": 0}
    counter_lock = threading.Lock()

    def read(item: tuple[str, str]) -> list[dict]:
        q, url = item
        with counter_lock:
            counter["n"] += 1
            n = counter["n"]
        _update(task_id, pid, progress=f"Reading {domain(url)}, {n} of {total} pages")
        try:
            page = browser.fetch(url)
        except browser.FetchError:
            return []
        if not page.text.strip():
            return []
        try:
            return extract_findings(question, q, page)
        except Exception:  # noqa: BLE001 - a bad model reply for one page is skippable
            return []

    findings: list[dict] = []
    if plan_pages:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research-read") as pool:
            for got in pool.map(read, plan_pages):
                findings.extend(got)
    _check(task_id)

    findings = dedupe(findings)
    _update(task_id, pid, status="synthesizing", progress=f"Synthesizing {len(findings)} findings")
    summary = synthesize(question, context, findings)
    _check(task_id)

    with _write_lock, session_scope() as s:
        t = s.get(ResearchTask, task_id)
        if not t or t.status == "cancelled":
            raise Cancelled()
        for f in findings:
            s.add(ResearchSource(task_id=task_id, url=f["url"], title=f["title"][:300],
                                 excerpt=f["excerpt"], note=f["claim"], reliability=f["reliability"]))
            if f["reliability"] >= MEMORY_THRESHOLD:
                s.add(Memory(project_id=pid, agent_id=None, kind="research", chapter=chapter,
                             content=f"{f['claim']} (source: {domain(f['url'])})",
                             source=f"research:{task_id}", importance=f["reliability"]))
        t.summary = summary
        t.status = "done"
        domains = len({domain(f["url"]) for f in findings})
        t.progress = f"Read {total} pages across {domains} sites, kept {len(findings)} sources"
        t.finished_at = now()
        s.add(t)
    events.publish(pid, "research.updated", {"id": task_id, "status": "done"})
    if any(f["reliability"] >= MEMORY_THRESHOLD for f in findings):
        events.publish(pid, "memory.created", {"source": f"research:{task_id}"})
    return {"task_id": task_id, "sources": len(findings), "pages": total, "queries": subs}


# ------------------------------------------------------------------ entry points

def create(session: Session, project_id: str, question: str, chapter: Optional[int]) -> ResearchTask:
    task = ResearchTask(project_id=project_id, question=question.strip(), chapter=chapter,
                        status="queued", progress="Queued")
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def submit(project_id: str, task_id: str, chapter: Optional[int] = None) -> None:
    events.publish(project_id, "research.updated", {"id": task_id, "status": "queued"})
    fn = lambda _run_id: run_task(task_id)  # noqa: E731
    if SYNC:
        try:
            jobs.run_inline(fn)
        except Exception:  # noqa: BLE001 - failure is recorded on the task
            pass
    else:
        jobs.submit(project_id, "research", fn, chapter=chapter, input={"task_id": task_id})


def active_workers() -> int:
    return sum(_active.values())


def list_sources(session: Session, task_id: str) -> list[ResearchSource]:
    return list(session.exec(select(ResearchSource).where(ResearchSource.task_id == task_id)
                             .order_by(ResearchSource.reliability.desc())).all())
