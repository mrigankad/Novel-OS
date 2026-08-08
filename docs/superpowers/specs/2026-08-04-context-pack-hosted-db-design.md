# Context Pack + Hosted DB Readiness Design

**Date:** 2026-08-04  
**Status:** Approved (user: “Approve” on A+B design)  
**Scope:** Approach A (structured chapter context) + Approach B (Postgres-ready API DB).  
**Explicitly deferred:** Vector database / embeddings / RAG (revisit at P4 semantic collections).

**Related:** `PLAN.md` P2/P4; `docs/ARCHITECTURE.md`; commercial design §4.1 (files = story truth).

---

## 1. Problem

Agents today get context by **dumping then truncating**:

- Guardian validates only the first ~5 000 characters of a chapter.
- Codex is concatenated then cut at ~2 000–4 500 characters — later entries vanish.
- Architect/Scribe keep cast to “appeared in last 3 chapters” and plot threads to top 5.
- Prior chapters are placeholders, not real synopses.
- Continue-chat uses a 2 500-character tail with almost no world model.

Separately, the API DB is SQLite-by-default with a tenancy schema that is *meant* to run on Postgres later, but there is no documented URL flip, dialect guard, or search path that survives that flip.

**Authors feel this as:** agents forgetting dormant cast, ignoring Codex rules, and “missing” mid-chapter continuity. Hosting will feel it as a painful SQLite→Postgres rewrite if we wait.

---

## 2. Goals

1. **Right facts for this chapter** — ranked, budgeted context packs replace blind truncation.
2. **Deterministic + typed world model stays first-class** — Codex IDs, relationship edges, plot threads; not cosine similarity.
3. **Files remain story truth** — `story_state.json` + manuscript stages stay canonical for the agent engine.
4. **API DB can become Postgres** by changing `NOVEL_OS_DB` without redesigning the story model.
5. **Keyword search without vectors** — optional FTS over Codex names / chapter titles with an API shape that ports to Postgres later.

## 3. Non-goals

- Embeddings, Chroma, Pinecone, pgvector, FAISS, or any second “memory” database.
- Moving story state into SQL.
- Multi-tenant auth UI / billing (still P7).
- S3 media cutover (keep local content-addressed store; interface already abstracted).
- Rewriting agent system prompts’ personalities — only the *user* prompt assembly changes.
- Full manuscript semantic search (“scenes that feel like betrayal”) — deferred with vectors.

---

## 4. Principles

1. **Filter then budget, never dump then chop.** Rank items; drop lowest rank when over budget.
2. **IDs over vibes.** Packs cite character/codex/edge/thread ids so continuity and UI can deep-link.
3. **One pack builder, many consumers.** Architect, Scribe, Guardian, continue-chat, consequence preview all call the same builder with a `purpose` flag that only changes budgets/slots.
4. **Additive engine changes.** Existing `format_codex_block` may remain as a thin wrapper over the pack for a release, then deprecate.
5. **SQLModel dialect neutrality.** Prefer portable types/queries; document known SQLite-only shortcuts if any remain.

---

## 5. Approach A — Chapter context pack

### 5.1 Module

**New:** `core/context_pack.py`

```text
build_context_pack(state: StoryState, chapter: int, *, purpose: PackPurpose) -> ContextPack
format_context_pack(pack: ContextPack, *, max_chars: int | None = None) -> str
```

`PackPurpose`: `architect` | `scribe` | `guardian` | `continue` | `consequence`.

### 5.2 Pack shape

```json
{
  "chapter": 4,
  "purpose": "guardian",
  "cast": [
    {"id": "char_001", "name": "Lena", "role": "protagonist", "why": "pov", "rank": 100}
  ],
  "bonds": [
    {"id": "rel-012", "source_id": "…", "target_id": "…", "label": "rivals", "rank": 80}
  ],
  "threads": [
    {"id": "…", "name": "…", "status": "active", "priority": 5, "rank": 90}
  ],
  "prior_chapters": [
    {"number": 3, "title": "…", "synopsis": "…"},
    {"number": 2, "title": "…", "synopsis": "…"}
  ],
  "codex": [
    {"id": "…", "entry_type": "location", "name": "Pier", "summary": "…", "rank": 70}
  ],
  "budgets": {"max_chars": 6000, "used_chars": 4120},
  "dropped": [{"kind": "codex", "id": "…", "reason": "over_budget"}]
}
```

### 5.3 Ranking rules (v1)

**Cast inclusion (union):**

1. Chapter POV character  
2. Names appearing in chapter outline / synopsis / binder node title (simple case-insensitive name match against Codex)  
3. Characters with `last_appearance_chapter >= N - 5` (widen from 3 → 5)  
4. One-hop relationship neighbors of anyone already in cast  

**Bonds:** edges where `source_id` or `target_id` is in cast; hostile labels (`enemy`, `rival`, …) ranked higher for Guardian.

**Threads:** active (and foreshadowed for Guardian) threads that mention cast names or are priority ≥ 3; sort by priority desc, then recency.

**Prior chapters:** binder/chapter synopsis for `N-1` and `N-2`. If synopsis empty, use a deterministic one-liner from chapter title + POV + status (no LLM required in v1). Optional later: Architect-generated synopsis refresh already exists for corkboard — reuse when present.

**Codex (non-character):** locations/items/world entries whose names appear in outline/synopsis/prior synopsis, plus entries tagged/linked to cast if such links exist; otherwise include high-signal worldbuilding with short summaries until budget fills.

### 5.4 Budgets (defaults; tunable)

| Purpose | Max pack chars | Notes |
|---|---|---|
| `architect` | 5 000 | Cast + threads + prior; light Codex |
| `scribe` | 6 000 | Outline already separate; pack supplements |
| `guardian` | 7 000 | Dense bonds + Codex rules |
| `continue` | 3 000 | Tail of prose stays separate |
| `consequence` | 2 500 | Matches today’s tight preview |

When over budget: drop lowest `rank` first; record in `dropped` for debug/tests. **Never** silent mid-string truncation of a kept entry’s core name/id line — summaries may shorten.

### 5.5 Guardian chapter text

Replace hard `chapter_text[:5000]` with one of:

1. **Preferred v1:** send full chapter if under ~12 k chars; otherwise send **overlapping windows** (e.g. 4 k with 400 overlap) in one prompt labeled Part 1/2/… *or* run deterministic checks on full text (already free) and only send LLM the pack + a structured assertion list.  
2. **Minimum bar:** if still truncating for the LLM, truncate from a **middle-aware** strategy is wrong — prefer end+start slices with explicit “middle omitted” note, and rely on deterministic engine for the full file.

**Decision locked for v1:**  
- Deterministic `continuity_engine.run_all` always sees full chapter files (already true if it reads files).  
- LLM Guardian prompt: include **full text up to 12 000 chars**; if longer, include **start 6 000 + end 4 000** with an explicit omission marker, plus the context pack. Revisit chunked multi-call only if quality demands it.

### 5.6 Wiring

| Consumer | Change |
|---|---|
| `orchestrator._generate_architect_outline_prompt` | Use `format_context_pack(..., purpose=architect)` instead of ad-hoc last-3 / top-5 loops |
| `orchestrator._generate_chapter_prompt` (Scribe) | Same |
| `orchestrator.validate_chapter` (Guardian) | Pack + new chapter-text policy |
| `StoryState.get_continuity_context` | Prefer pack-derived `codex_block` / relationships subset |
| `api/services.py` continue + consequence | Inject compact pack |

### 5.7 Tests

- Fixture manuscript with > budget Codex entries → pack keeps POV + linked rivals, drops low-rank filler; `dropped` non-empty.  
- Hostile edge to cast appears in Guardian pack.  
- Prior synopsis slot filled from binder.  
- Orchestrator dry-run / unit tests assert pack sections present in prompt strings.  
- No regression: empty project still produces empty/minimal pack without crashing.

---

## 6. Approach B — Hosted DB readiness

### 6.1 Contract (unchanged product rule)

| Concern | Store |
|---|---|
| Story state, outlines, draft/revised markdown | Project filesystem |
| Final ProseMirror, snapshots, comments, media metadata, tenancy | SQL (SQLite now, Postgres later) |
| Media bytes | Local FS now; S3-compatible later |

### 6.2 Configuration

- Document in `.env.example` and `docs/ARCHITECTURE.md`:

```bash
# SQLite (default, local)
NOVEL_OS_DB=sqlite:///./novel_os.db

# Postgres (hosted)
# NOVEL_OS_DB=postgresql+psycopg://user:pass@host:5432/novel_os
```

- `api/db.py` `configure()` already takes URL; ensure engine kwargs are dialect-safe (e.g. `check_same_thread` only for SQLite).

### 6.3 Dialect hygiene

- Audit `api/db.py` for SQLite-only SQL; gate or replace.  
- Add `tests/test_db_dialect.py` (or extend existing): with SQLite URL, create tables + round-trip Project/Chapter/Artifact.  
- Optional CI job later with Postgres service — **not required to merge this slice**; document manual smoke steps.

### 6.4 Keyword FTS (optional in same slice if time; else immediate follow-on)

- **SQLite:** FTS5 virtual table over Codex entry names + chapter titles (mirrored on ingest / Codex write).  
- **API:** `GET /api/projects/{id}/search?q=` returning typed hits `{kind, id, label, chapter?}`.  
- **Postgres later:** `tsvector` / `websearch_to_tsquery` behind the same route.  
- UI: wire into ⌘K as a follow-up; not blocking pack work.

### 6.5 What we will not do in B

- Mandate Postgres for local dev.  
- Dual-write story JSON into SQL.  
- Introduce Redis, message buses, or separate search appliances.

---

## 7. Vector database (deferred)

**Do not add** until:

1. Context packs + FTS ship, and  
2. Authors still need “find scenes like this” / research RAG (P4), and  
3. Hosted Postgres exists so **pgvector** can live beside tenancy tables (one database, not a sidecar).

Until then, “memory” = structured `StoryState` + packs + deterministic continuity.

---

## 8. Rollout sequence

1. `context_pack` module + unit tests  
2. Wire Architect / Scribe / Guardian  
3. Wire continue + consequence  
4. DB URL docs + SQLite-only guard + dialect smoke test  
5. (Follow-on) FTS search endpoint  
6. Update `PLAN.md` / `ARCHITECTURE.md` status lines  

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Name-matching false positives for cast | Prefer exact full-name match; require length ≥ 3; POV/outline wins over fuzzy |
| Pack still too large for small models | Purpose budgets; `dropped` visibility in dry-run |
| Prompt drift vs agent system prompts | Only change user/context assembly; keep `agents/*/prompt.md` stable |
| Postgres surprises | Dialect test + documented smoke; no silent SQLite functions |
| Scope creep into RAG | Hard non-goal; vectors only at P4 revisit |

---

## 10. Success criteria

- [ ] Guardian/Scribe prompts for a fixture novel include dormant-but-linked rival and omit truncated filler Codex noise.  
- [ ] Chapter longer than 5 k chars is not silently “prefix-only” for Guardian without an omission marker.  
- [ ] `NOVEL_OS_DB` Postgres URL documented; SQLite path unchanged for local.  
- [ ] `pytest` green for pack + existing API suites.  
- [ ] No new vector/embedding dependency in `requirements.txt`.

---

## 11. Open points (resolved defaults)

| Point | Default |
|---|---|
| Last-appearance window | 5 chapters |
| Prior chapters count | 2 |
| Guardian LLM text | Full ≤12 k; else head 6 k + tail 4 k + marker |
| FTS in same PR as packs | Prefer packs first; FTS immediate follow-on if slice runs long |
| Commit of this spec | On request (repo commit policy) |
