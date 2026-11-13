"""Agent memory: remember things, recall the right ones.

recall() is a hybrid ranker: a SQL prefilter (project, shared + own, capped at
~500 rows) followed by Python scoring that blends BM25-lite keyword overlap,
importance, recency, a pinned boost and chapter proximity. If the studio's
default provider is Ollama and an embedding model answers, cosine similarity is
blended in too; otherwise embeddings are skipped silently.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlmodel import Session, select

from .. import events
from ..models import Connection, Memory
from ..models.base import now

KINDS = ("fact", "decision", "preference", "episode", "summary", "style", "research")
MAX_CANDIDATES = 500

STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have he her hers him his
how i if in into is it its just me my no not of on or our she so than that the their them then there
these they this those to too us was we were what when where which who whom why will with would you
your yours about after again all also any because before being both each few more most other over
own same should some such through under until up very off once only out here while during against
between above below down further nor ours ourselves themselves itself yourself myself herself himself
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9']+")

W_KEYWORD, W_IMPORTANCE, W_RECENCY, W_PROXIMITY, W_EMBED, PIN_BOOST = 0.45, 0.2, 0.1, 0.15, 0.25, 0.6


def tokens(text: str) -> list[str]:
    out = []
    for t in _TOKEN_RE.findall((text or "").lower()):
        t = t.strip("'")
        if len(t) > 1 and t not in STOPWORDS:
            out.append(t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t)
    return out


# ---- optional embeddings ------------------------------------------------------

_embed_disabled = False


def _embed(session: Session, text: str) -> Optional[list[float]]:
    """Embedding from a local Ollama model, or None (fast, silent fallback)."""
    global _embed_disabled
    if _embed_disabled or os.environ.get("NOVEL_OS_NO_EMBED"):
        return None
    conn = session.exec(select(Connection).where(Connection.is_default == True)).first()  # noqa: E712
    if not conn or conn.provider != "ollama":
        return None
    base = (conn.base_url or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    model = os.environ.get("NOVEL_OS_EMBED_MODEL", "nomic-embed-text")
    try:
        req = urllib.request.Request(f"{base}/api/embed", data=json.dumps({"model": model, "input": text[:4000]}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:  # noqa: S310 - local provider
            data = json.loads(r.read())
        vec = (data.get("embeddings") or [None])[0]
        return vec if vec else None
    except Exception:  # noqa: BLE001 - no model pulled, server down: just skip
        _embed_disabled = True
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---- API ------------------------------------------------------------------------

def remember(session: Session, project_id: str, kind: str, content: str, agent_id: Optional[str] = None,
             chapter: Optional[int] = None, source: str = "", importance: float = 0.5,
             pinned: bool = False, commit: bool = True) -> Memory:
    content = (content or "").strip()
    m = Memory(project_id=project_id, agent_id=agent_id, kind=kind if kind in KINDS else "fact",
               content=content, chapter=chapter, source=source,
               importance=max(0.0, min(1.0, float(importance))), pinned=pinned,
               embedding=_embed(session, content))
    session.add(m)
    if commit:
        session.commit()
        session.refresh(m)
    else:
        session.flush()
    events.publish(project_id, "memory.created", {"id": m.id, "kind": m.kind, "agent_id": agent_id})
    return m


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return now()
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def score_memories(cands: list[Memory], query: str, chapter: Optional[int] = None,
                   query_vec: Optional[list[float]] = None) -> list[tuple[float, Memory]]:
    q = set(tokens(query))
    docs = [Counter(tokens(m.content)) for m in cands]
    n = len(docs) or 1
    avg_len = (sum(sum(d.values()) for d in docs) / n) or 1.0
    df = Counter()
    for d in docs:
        df.update(set(d) & q)
    k1, b = 1.2, 0.75
    raw = []
    for d in docs:
        dl = sum(d.values()) or 1
        s = 0.0
        for t in q:
            tf = d.get(t, 0)
            if tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avg_len))
        raw.append(s)
    top = max(raw) if raw and max(raw) > 0 else 1.0
    t_now = now()
    out = []
    for m, kw in zip(cands, raw):
        age_days = max(0.0, (t_now - _aware(m.created_at)).total_seconds() / 86400)
        recency = math.exp(-age_days / 30)
        if chapter is not None and m.chapter is not None:
            prox = 1 / (1 + abs(chapter - m.chapter))
        else:
            prox = 0.3 if m.chapter is None else 0.0
        s = W_KEYWORD * (kw / top) + W_IMPORTANCE * m.importance + W_RECENCY * recency + W_PROXIMITY * prox
        if m.pinned:
            s += PIN_BOOST
        if query_vec and m.embedding:
            s += W_EMBED * max(0.0, _cosine(query_vec, m.embedding))
        out.append((s, m))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def recall(session: Session, project_id: str, query: str, agent_id: Optional[str] = None,
           chapter: Optional[int] = None, k: int = 12, touch: bool = True) -> list[Memory]:
    stmt = select(Memory).where(Memory.project_id == project_id)
    if agent_id:
        stmt = stmt.where(or_(Memory.agent_id == None, Memory.agent_id == agent_id))  # noqa: E711
    else:
        stmt = stmt.where(Memory.agent_id == None)  # noqa: E711
    stmt = stmt.order_by(Memory.pinned.desc(), Memory.importance.desc(), Memory.created_at.desc()).limit(MAX_CANDIDATES)
    cands = list(session.exec(stmt).all())
    if not cands:
        return []
    qvec = _embed(session, query) if any(m.embedding for m in cands) else None
    picked = [m for _, m in score_memories(cands, query, chapter, qvec)[:k]]
    if touch and picked:
        ts = now()
        for m in picked:
            m.recall_count += 1
            m.last_recalled_at = ts
            session.add(m)
        session.commit()
        for m in picked:
            session.refresh(m)
    return picked


# ---- extraction helpers ------------------------------------------------------------

_BLOCK_RE = re.compile(r"\[(\w+_STATE_UPDATE)\](.*?)\[/\1\]", re.S)


def parse_block_fields(text: str, tag: str) -> dict[str, list[str]]:
    """Parse a `[TAG] Field:\n  - item [/TAG]` contract block into {field: [items]}."""
    m = re.search(rf"\[{tag}\](.*?)\[/{tag}\]", text or "", re.S)
    if not m:
        return {}
    fields: dict[str, list[str]] = {}
    cur = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        head = re.match(r"^\s*([A-Za-z_]+):\s*(.*)$", line)
        if head and not line.lstrip().startswith("-"):
            cur = head.group(1)
            fields[cur] = []
            rest = head.group(2).strip()
            if rest and rest != "[None]":
                fields[cur].append(rest)
        elif cur:
            item = line.strip().lstrip("-").strip()
            if item and item != "[None]":
                fields[cur].append(item)
    return fields


def facts_from_scribe(text: str) -> list[str]:
    f = parse_block_fields(text, "SCRIBE_STATE_UPDATE")
    if not f:
        return []
    out = f.get("New_Information_Revealed", []) + f.get("Key_Events", [])[:4] + \
        [f"Foreshadowing planted: {x}" for x in f.get("Foreshadowing_Planted", [])]
    return [x for x in out if x][:10]
