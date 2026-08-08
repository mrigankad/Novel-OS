# Novel OS — Full-Stack Architecture and Remaining Buildout

**Written:** 2026-08-08
**Baseline commit:** `27b7865` (P1–P4 buildout committed, all suites green)
**Supersedes nothing.** This is the storage/architecture companion to [`PLAN.md`](../../../PLAN.md),
which stays the phase board. PLAN.md says *what ships when*; this says *where every
byte lives and why*.

---

## 1. The one decision everything else follows from

**Story truth is files. SQL is an index and a collaboration surface. Blobs are content-addressed.**

Three stores, each with a job it is uniquely good at, and a hard rule about what
must never move between them:

| Store | Holds | Authority | Lost if deleted |
|---|---|---|---|
| **Filesystem** (`NOVEL_OS_PROJECTS_DIR`) | `story_state.json`, per-chapter stage markdown (`outline`/`draft`/`revised`/`final`) | **Canonical.** The agent engine reads and writes only this. | The novel |
| **SQL** (`NOVEL_OS_DB`, SQLModel) | Project/chapter registry, `Artifact` stage text, snapshots, comments, media metadata, tenancy | **Derived**, except comments + tenancy | Comments, snapshots, sharing — recoverable prose |
| **Blob store** (`MediaStore`) | Images, keyed by SHA-256 of their bytes | Canonical for pixels | Portraits and research images |

The reason this is not a hedge: the agent pipeline is a mature file-based engine
that writes `chapter_NNN_*.md`. Making it DB-native buys nothing a writer can
feel, and costs a rewrite of the one part of the system that already works. So
the DB indexes the files rather than replacing them, and `db.ingest_project()`
is the bridge.

**What must never happen:** SQL becoming the only place a chapter exists. If the
database is dropped, `pytest` and the CLI must still produce the novel from disk.
Any feature that would break that invariant is the wrong feature.

---

## 2. Layer map, as built

```
web/  React 19 · Vite · Tailwind v4 · TipTap
  routes/     ProjectsList · ProjectDashboard · ChapterView
              RelationshipChart · ResearchMoodboard · Settings
  components/ RichTextEditor (ProseMirror) · Inspector · BinderNav
              Corkboard · Outliner · CommandPalette · Consequence…
  lib/        richText · binderReorder · genres · bonds · chapterBadges
  hooks/      useLatestRef · useMediaQuery · useRunPhase
        │ HTTP/JSON, polls /jobs/{id}
api/  FastAPI
  routes.py     52 endpoints (see §3)
  services.py   ProjectService — the only thing that touches both stores
  db.py         SQLModel: 11 tables, PRAGMA-based additive migrations
  media.py      MediaStore ABC → LocalMediaStore (dev) | S3 (prod, unbuilt)
  richtext.py   ProseMirror JSON ⇄ markdown projection
  jobs.py       JobRunner (threads) — agents never run inside a request
  tenancy.py    Workspace/User/Membership resolution
        │ reads/writes files
core/  the engine (file-based, provider-agnostic)
  orchestrator · state_manager · continuity_engine · context_pack
  consequence · chapter_metrics · style_stats · prose_sanitize
  document_tree · setup_wizard · llm_client
```

### Boundaries that are load-bearing

- **`ProjectService` is the only bridge.** Routes never touch the filesystem;
  `core/` never imports `api/`. Breaking this is how the two stores drift.
- **Agents run in `JobRunner`, never in a request.** An HTTP handler that blocks
  on an LLM is a timeout waiting to happen and makes cancellation impossible.
- **Only Final is user-mutable.** `outline`/`draft`/`revised` are immutable
  provenance. Every AI output gets a diff with accept/reject.
- **Agent prompts are never edited to suit the UI.** If the UI needs different
  context, that is a `context_pack.py` change, not a `agents/*/prompt.md` change.

---

## 3. The API surface, by concern

52 endpoints today. Grouped so gaps are visible:

| Concern | Endpoints | State |
|---|---|---|
| Projects | `GET/POST /projects`, `GET/PATCH /projects/{id}`, `POST /projects/sample` | ✅ |
| Pipeline | `POST /{id}/run`, `GET /jobs/{job_id}`, `GET /{id}/chapters/{n}/stages` | ✅ |
| Final (rich text) | `GET/PUT /{id}/chapters/{n}/final/doc`, `PUT …/final`, `POST …/final/promote` | ✅ |
| Binder | `GET /{id}/binder`, `POST …/binder/move`, `PATCH …/binder/{node}` | ✅ |
| Codex + bonds | `GET/POST /{id}/codex`, `PUT …/codex/{e}/portrait`, `GET/POST/DELETE /{id}/relationships` | ✅ |
| Continuity | `GET /{id}/continuity`, `GET /{id}/chapters/{n}/continuity` | ✅ |
| Review + history | snapshots ×5, comments ×4 | ✅ |
| Media | `GET/POST /{id}/media`, `PATCH/DELETE …/{mid}`, `GET …/{mid}/raw` | ✅ |
| Search + collections | `GET /{id}/search`, collections ×4 | ✅ keyword only |
| Analytics | `GET /{id}/statistics` | ✅ |
| Export | `GET /{id}/export` | ◐ **markdown only** |
| Studio settings | `GET/PUT /studio/llm` | ✅ |
| **Auth** | — | ☐ **none** |
| **Billing** | — | ☐ **none** |

Two real gaps, both P6/P7: export is markdown-only, and there is no
authentication despite the tenancy schema existing to receive it.

---

## 4. Storage, concretely

### 4.1 Filesystem

```
$NOVEL_OS_PROJECTS_DIR/
  <project-id>/                 # default workspace: flat, no migration needed
  ws-<slug>/<project-id>/       # other workspaces namespaced
    outputs/
      state/story_state.json    # cast, bonds, threads, codex, document tree
      manuscript/
        chapter_001_outline.md
        chapter_001_draft.md    # immutable provenance
        chapter_001_revised.md  # immutable provenance
        chapter_001_final.md    # markdown projection of the PM doc
```

Writes are atomic (temp + rename). Project ids are pattern-validated before any
path is built, so `..`, separators, and drive letters cannot escape a workspace;
a traversing id returns 404, indistinguishable from a missing project.

### 4.2 SQL — 11 tables

`Project`, `Chapter`, `Artifact`, `Snapshot`, `Comment`, `Media`, `Workspace`,
`User`, `Membership`, `ProjectOwnership`, `AuthSession`.

Runs on SQLite today and Postgres by changing `NOVEL_OS_DB`; `_connect_args_for()`
applies SQLite-only args only to `sqlite:` URLs. Schema changes are **additive** —
`db.configure()` runs a PRAGMA-based ALTER-TABLE list because `create_all` will
not alter an existing table.

### 4.3 Blobs

Content-addressed on SHA-256, so re-uploading a duplicate is free and served URLs
are immutably cacheable. The user's filename is metadata and never touches the
path, which removes traversal as a *category* rather than filtering for it. SVG is
deliberately rejected — it carries script and would execute if served inline.

**Not built:** the S3 implementation behind `MediaStore`. The ABC exists; only
`LocalMediaStore` is written. This is the single largest hosting blocker.

---

## 5. What should be there — and what should not

Being explicit about the *nots* is the point of this document.

### Belongs

| Thing | Why |
|---|---|
| Files as canonical story truth | The engine works; a DB rewrite buys the writer nothing |
| ProseMirror JSON for Final + markdown projection | Track changes and export fidelity need a real doc model; agents keep reading markdown |
| Deterministic continuity before AI inference | The moat. AI-guessed consequences are labelled *predicted*, never fact |
| Job registry for agents | Cancellable, pollable, and never blocks a request |
| Content-addressed blobs | De-dupe and cacheability for free |
| Additive migrations | The user's local install must never need a manual step |
| In-house SVG for analytics | A chart library is 100 kB to draw six rings |

### Does not belong

| Thing | Why not |
|---|---|
| **A vector DB / embeddings** | Ranked context packs already beat dump-and-truncate. Semantic search is a P4 tail item, not infrastructure. Adding pgvector now is an ops dependency with no consumer |
| **Postgres before there is a deployment** | The schema is already portable. Adopting it early adds ops burden and zero user-visible value |
| **Real-time multi-user collaboration (CRDT/OT)** | Deliberately out of scope. Collaboration ships as *comment personas* (author/editor/beta) on a single-writer model. CRDTs would be the largest subsystem in the product, for a market that mostly writes alone |
| **A chart library** | See above |
| **Agents writing Final directly** | Violates AI-proposes/human-disposes. Every AI output gets a review surface |
| **Storing prose only in SQL** | Breaks the invariant in §1 |
| **Server-side LLM key custody by default** | BYO-key and the subscription-CLI mode are the pricing wedge; holding keys turns a differentiator into a liability |
| **SVG uploads** | Script execution vector |

---

## 6. Remaining buildout, in order

### Now — close the P2 tail (small, high value)

- **R4 relationship checks** in `continuity_engine.py`: `since` violations,
  contradictory bonds, dead-character co-presence. The engine is the moat and
  these are the last three deterministic checks; the UI to show them
  (`RelationshipChart`, Inspector continuity tab) already exists.
- **Codex auto-extract as proposals.** Entities detected in prose surface as
  *suggestions requiring confirmation* — never silent writes.

### P5 — Word parity

Ordered by how much each depends on the ProseMirror work already done:

1. **Track changes / suggest mode.** ProseMirror marks with author attribution
   and per-change accept/reject. AI suggestions render as in-place marks — this
   is what P1 was load-bearing for.
2. **Styles system.** Named styles that drive compile output. Must land *before*
   P6, since the compiler consumes them.
3. **Spelling & grammar** with a per-project dictionary seeded from the Codex, so
   invented names stop being flagged.
4. **AI image generation.** New `core/image_client.py` mirroring `llm_client.py`'s
   provider-agnostic shape, preserving BYO-key.

### P6 — Publishing

Compile engine walks the document tree → DOCX / EPUB / PDF / HTML, with
front-matter and chapter titles drawn from state, inline images and styles
carried through. Validate EPUB against epubcheck. Export presets per target.

**Blocked on:** P5 styles. Compiling without a style system produces output that
has to be reformatted by hand, which is the exact gap Atticus fills.

### P7 — Commercial

1. **S3 `MediaStore`** — hosting blocker, do it first.
2. **Postgres cutover** — now it has a consumer.
3. **Auth** on the existing P0.5 tables: sign-up, sign-in, sessions, reset.
4. **Billing** — BYO-key and subscription-CLI tiers.
5. **Onboarding** — templates, sample project, genre-aware Architect scaffolding.
6. **Marketing site** leading with the three things nobody else has:
   deterministic continuity, pipeline provenance, consequence preview.

### Cross-cutting, worth doing soon

- **`.gitattributes` for line endings.** Every file currently shows as modified on
  a fresh checkout because of CRLF/LF churn. One `* text=auto eol=lf` line removes
  a permanent source of diff noise. Do it as a standalone commit — it rewrites the
  whole tree.
- **Bundle splitting.** `npm run build` warns that chunks exceed 500 kB. TipTap and
  `motion` are the obvious dynamic-import candidates.
- **`GET /health` should report store reachability**, not just liveness.

---

## 7. Standards every phase closes against

- Engine changes are additive and migrated; agent prompts are never rewritten for the UI.
- Writes are atomic; paths are validated, not sanitised.
- Drafts and AI revisions are immutable provenance.
- Every AI output has a diff with accept/reject — never a silent overwrite.
- Agents go through the job registry.
- Motion respects `prefers-reduced-motion`; fonts and assets are self-hosted.
- Every phase closes green: `pytest`, `vitest`, `npm run build`, `npm run lint`.
