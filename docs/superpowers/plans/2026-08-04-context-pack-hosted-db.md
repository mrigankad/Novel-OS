# Context Pack + Hosted DB Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace dump-then-truncate agent context with ranked chapter context packs, and make the API DB URL Postgres-ready without moving story truth out of files.

**Architecture:** New `core/context_pack.py` builds a ranked `ContextPack` from `StoryState` (cast, bonds, threads, prior synopses, Codex). Orchestrator and API services format that pack into prompts. `api/db.py` only applies SQLite `connect_args` when the URL is SQLite; docs show Postgres URL. Vectors stay deferred.

**Tech Stack:** Python 3.10+, existing `StoryState` / SQLModel / FastAPI / pytest. No new embedding deps.

## Global Constraints

- Files remain story truth (`story_state.json` + manuscript stages); SQL holds Final/comments/media meta/tenancy only.
- No vector/embedding packages in `requirements.txt`.
- Do not rewrite `agents/*/prompt.md` personalities — only user/context assembly.
- Filter then budget; never silent mid-entry name truncation.
- Guardian LLM text: full chapter if ≤12 000 chars; else head 6 000 + tail 4 000 + omission marker.
- Cast last-appearance window: 5 chapters; prior chapters: 2.
- Commits only when the user explicitly asks (do not auto-commit).

**Spec:** `docs/superpowers/specs/2026-08-04-context-pack-hosted-db-design.md`

---

## File map

| File | Responsibility |
|---|---|
| `core/context_pack.py` | Build + format ranked packs |
| `tests/test_context_pack.py` | Pack ranking, budget, prior synopsis |
| `core/state_manager.py` | Optional thin wrapper; `get_continuity_context` uses pack |
| `core/orchestrator.py` | Architect / Scribe / Guardian consume pack |
| `api/services.py` | continue + consequence inject pack |
| `api/db.py` | Dialect-safe `configure()` |
| `tests/test_db_dialect.py` | SQLite configure + create tables |
| `.env.example` | Document `NOVEL_OS_DB` SQLite + Postgres |
| `docs/ARCHITECTURE.md` | Short note on packs + DB URL |
| `PLAN.md` | Status line for context pack |

---

### Task 1: Context pack core (TDD)

**Files:**
- Create: `core/context_pack.py`
- Create: `tests/test_context_pack.py`

**Interfaces:**
- Produces:
  - `PackPurpose = Literal["architect", "scribe", "guardian", "continue", "consequence"]`
  - `@dataclass ContextPack` with fields: `chapter`, `purpose`, `cast`, `bonds`, `threads`, `prior_chapters`, `codex`, `budgets`, `dropped`
  - `build_context_pack(state: StoryState, chapter: int, *, purpose: PackPurpose) -> ContextPack`
  - `format_context_pack(pack: ContextPack, *, max_chars: int | None = None) -> str`
  - `slice_chapter_for_llm(text: str, *, soft_limit: int = 12000, head: int = 6000, tail: int = 4000) -> str`

- [x] **Step 1–4:** `core/context_pack.py` + `tests/test_context_pack.py` (5 passed)
- [x] Wire Architect / Scribe / Guardian + `get_continuity_context`
- [x] continue + consequence packs in `api/services.py`
- [x] `_connect_args_for` + `tests/test_db_dialect.py` + `.env.example` + ARCHITECTURE/PLAN notes
- [ ] FTS follow-on (deferred)

```python
# tests/test_context_pack.py
import sys
from pathlib import Path
_CORE = Path(__file__).resolve().parents[1] / "core"
sys.path.insert(0, str(_CORE))

from context_pack import build_context_pack, format_context_pack, slice_chapter_for_llm
from state_manager import Character, ChapterState, RelationshipEdge, StoryState, PlotThread

def _state(tmp_path):
    root = tmp_path / "proj"
    (root / "outputs" / "state").mkdir(parents=True)
    return StoryState(str(root))

def test_pack_keeps_pov_and_linked_rival_drops_filler(tmp_path):
    s = _state(tmp_path)
    s.add_character(Character(id="c1", full_name="Lena", role="protagonist",
                              last_appearance_chapter=4))
    s.add_character(Character(id="c2", full_name="Mara", role="antagonist",
                              last_appearance_chapter=1))  # dormant >5? use chapter 10
    s.add_character(Character(id="c3", full_name="Extra", role="minor",
                              last_appearance_chapter=1, notes="x" * 500))
    s.relationships["r1"] = RelationshipEdge(
        id="r1", source_id="c1", target_id="c2", label="rivals")
    s.chapters[10] = ChapterState(number=10, title="Clash", pov_character="Lena",
                                 status="planned")
    # Force low budget via format; build should still include Mara via bond
    pack = build_context_pack(s, 10, purpose="guardian")
    ids = {c["id"] for c in pack.cast}
    assert "c1" in ids and "c2" in ids

def test_slice_chapter_head_tail():
    text = "A" * 6000 + "M" * 2000 + "Z" * 4000
    out = slice_chapter_for_llm(text)
    assert out.startswith("A" * 100)
    assert out.endswith("Z" * 100)
    assert "omitted" in out.lower()
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
pytest tests/test_context_pack.py -v
```

- [ ] **Step 3: Implement `core/context_pack.py`**

Implement ranking per spec §5.3–5.5:
- Cast: POV + name hits in synopsis/outline fields + `last_appearance_chapter >= N-5` + 1-hop neighbors
- Bonds: edges touching cast; boost `enemy`/`rival`
- Threads: active, sort by priority
- Prior: chapters N-1, N-2 synopsis from `ChapterState` / binder if available; else `"{title} · POV {pov}"`
- `format_context_pack`: markdown sections; if over `max_chars` or purpose default budget, drop lowest rank into `dropped` then render
- Purpose default budgets: architect 5000, scribe 6000, guardian 7000, continue 3000, consequence 2500

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_context_pack.py -v
```

- [ ] **Step 5: Commit only if user asks**

---

### Task 2: Wire `get_continuity_context` + Guardian / Architect / Scribe

**Files:**
- Modify: `core/state_manager.py` (`get_continuity_context`, optionally deprecate dump path in `format_codex_block` by calling pack for chapter when known)
- Modify: `core/orchestrator.py` (`_generate_architect_outline_prompt`, `_generate_chapter_prompt`, `_generate_validation_prompt`)

**Interfaces:**
- Consumes: `build_context_pack`, `format_context_pack`, `slice_chapter_for_llm`
- Produces: prompts containing `## Context pack` (or equivalent) instead of raw last-3 / `[:5000]` only

- [ ] **Step 1: Failing test for validation prompt slice**

Add to `tests/test_context_pack.py` or new `tests/test_orchestrator_context.py`: build a mini orchestrator state with long chapter text; call `_generate_validation_prompt` and assert `"omitted"` when text > 12k, and assert rival name appears when edge exists.

- [ ] **Step 2: Run — FAIL or assert old `[:5000]` behavior**

- [ ] **Step 3: Implement wiring**

In `_generate_validation_prompt`:
```python
from context_pack import build_context_pack, format_context_pack, slice_chapter_for_llm
pack = build_context_pack(self.state, chapter_number, purpose="guardian")
body = slice_chapter_for_llm(chapter_text)
pack_md = format_context_pack(pack)
# Use body instead of chapter_text[:5000]; append pack_md; keep checklist
```

In Architect/Scribe prompts: replace the character last-3 loops and `active_threads[:5]` with `format_context_pack(build_context_pack(..., purpose="architect"|"scribe"))`.

`get_continuity_context`: set `'codex_block': format_context_pack(build_context_pack(self, chapter, purpose="guardian"))` and subset relationships from pack bonds.

- [ ] **Step 4: pytest targeted suites green**

```bash
pytest tests/test_context_pack.py tests/test_relationship_continuity.py tests/test_codex_guardian.py -v
```

---

### Task 3: API continue + consequence packs

**Files:**
- Modify: `api/services.py` (`continue_paragraph`, consequence preview path that calls `format_codex_block(max_chars=2000)`)

- [ ] **Step 1:** Locate both call sites; write/adjust test in `tests/test_consequence_api.py` or continue tests asserting prompt/context includes pack section when characters exist (if prompts are returned) — otherwise unit-test a small helper used by services.

- [ ] **Step 2:** Replace `format_codex_block(max_chars=2000)` with:
```python
from context_pack import build_context_pack, format_context_pack
pack = build_context_pack(s, number, purpose="continue")  # or consequence
codex = format_context_pack(pack, max_chars=2500)
```

- [ ] **Step 3:** `pytest tests/test_consequence_api.py tests/test_api.py -v` (subset that covers continue if any)

---

### Task 4: DB dialect readiness

**Files:**
- Modify: `api/db.py` `configure()`
- Create: `tests/test_db_dialect.py`
- Modify: `.env.example`
- Modify: `docs/ARCHITECTURE.md` (short paragraph)

- [ ] **Step 1: Failing test**

```python
def test_configure_sqlite_check_same_thread(tmp_path):
    from api import db
    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    db.configure(url)
    # create tables + insert Project
    ...
def test_configure_rejects_bogus_without_sqlite_args_on_postgres_url():
    # Don't require live Postgres: assert connect_args logic via helper
    from api.db import _connect_args_for
    assert _connect_args_for("sqlite:///./x.db") == {"check_same_thread": False}
    assert _connect_args_for("postgresql+psycopg://u:p@h/db") == {}
```

- [ ] **Step 2:** Implement `_connect_args_for(url: str) -> dict` and use in `configure`.

- [ ] **Step 3:** Document in `.env.example`:

```bash
# API database (SQLModel). Story manuscripts stay on the filesystem.
# NOVEL_OS_DB=sqlite:///./novel_os.db
# NOVEL_OS_DB=postgresql+psycopg://user:pass@localhost:5432/novel_os
```

- [ ] **Step 4:** `pytest tests/test_db_dialect.py -v`

---

### Task 5: Docs status (no FTS in this slice)

FTS is follow-on per spec §8 step 5 — skip unless Tasks 1–4 finish early.

- [ ] Update `PLAN.md` status board note: context pack ◐/✅ under moat / cross-cutting
- [ ] Update `docs/ARCHITECTURE.md` with context pack + `NOVEL_OS_DB` note
- [ ] Run full: `pytest tests/test_context_pack.py tests/test_db_dialect.py tests/test_relationship_continuity.py tests/test_codex_guardian.py tests/test_consequence_api.py -v`

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| `build_context_pack` / format / budgets | 1 |
| Ranking cast/bonds/threads/prior/codex | 1 |
| Guardian slice policy | 1 + 2 |
| Architect/Scribe wiring | 2 |
| continue/consequence | 3 |
| Postgres URL docs + dialect-safe engine | 4 |
| No vectors | Global constraint |
| FTS | Deferred follow-on |

---

## Execution

Preferred: **inline execution** in this session (user said continue). Skip auto-commits unless requested.
