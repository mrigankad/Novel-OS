# Novel OS as a Commercial Product — Design

**Date:** 2026-07-31
**Status:** Approved design. Supersedes the positioning sections of `plans/2026-06-10-novel-os-frontend-product-roadmap.md`; that document's engine analysis (§3) remains valid and is carried forward.
**Scope:** Master design for turning Novel OS from a local multi-agent CLI + dashboard into a sellable product.

---

## 1. Baseline — what exists today

Verified against the working tree on `dev` at commit `5f95009`.

**Engine (`core/`)**
- Five agent prompts (Architect, Scribe, Editor, Continuity Guardian, Style Curator), each with a strict OUTPUT CONTRACT producing machine-parseable blocks.
- `state_manager.py` — `StoryState` dataclasses persisted as a single JSON document with atomic writes and `.bak` rollback.
- `state_parser.py` — extracts `[*_STATE_UPDATE]` blocks from agent output and mutates state.
- `continuity_engine.py` — nine deterministic checks (dormant/overdue threads, unresolved foreshadowing, absent/never-appeared characters, dead-character state, missing chapter files, status drift, thin characters).
- `llm_client.py` — provider abstraction over 13+ backends including the Claude Code CLI (runs on a subscription with no per-token charge).
- `orchestrator.py` — CLI covering init / character / plot / plan / write / edit / validate / check / approve / status / export.

**API (`api/`)** — FastAPI with SQLite persistence: projects list/create, character add, run-phase as background jobs, chapter detail and stages, promote/edit/save Final, snapshot create/list/get/restore/delete, comment CRUD, markdown export, raw state.

**Web (`web/`)** — React 19, Tailwind v4, Vite 8. Projects list, project dashboard with chapter board and Cast section, ChapterView with a CodeMirror markdown editor (autosave, focus mode, find & replace), diff view, snapshots panel, comments, Outliner, ⌘K command palette, breadcrumbs, error boundary, confirm dialogs, light/dark theming.

**Not present**, despite a stale project memory claiming otherwise: Story Bible, Character Hub, Timeline, Scene Board, Analytics, Publishing Center/`api/exporters.py`, AI Assistant chat, Research workspace, mobile bottom nav. That work is not recoverable and is treated here as still to be built.

**Working tree is dirty:** 35 files with a repo-wide em-dash strip (286 insertions / 286 deletions). Cosmetic; commit or discard before P0 begins.

---

## 2. Market analysis

### 2.1 The field

| Tool | Strength | Fatal gap | Price |
|---|---|---|---|
| Scrivener | Structure king — binder, corkboard, outliner, snapshots, collections, compile, writing history, copyholders | Zero AI. Desktop-bound, dated UI, weak cloud/collaboration | ~$60 once |
| Atticus | Formatting and export — 17 templates, publish-ready PDF/EPUB, per-element typography control | No planning features at all; not a drafting environment | $147 once |
| Dabble | Cleanest cloud drafting; Plot Grid for storylines, character arcs, subplots | Shallow worldbuilding; thin AI | subscription |
| Plottr | Timeline and template-driven outlining | Planning only — you export to Scrivener or Word to write | subscription |
| Campfire | Deepest worldbuilding — relationship webs, interactive timeline, conlang dictionary; modular pricing | Modules sold separately; weak manuscript editor | per-module |
| Sudowrite | Best raw prose (Muse model fine-tuned on fiction); strong Describe/Dialogue tools; Story Bible | No persistent memory across sessions — context must be re-established every sitting | $29/mo |
| NovelCrafter | "Photoshop of AI fiction" — Codex with automatic context injection, scene beats, grid/matrix/outline planning, Workshop Chat, BYO API keys via OpenRouter | Heavy setup friction; chat cannot see scene content; reported crashes without saving and cleared Codex descriptions; rigid act/chapter/scene structure hostile to discovery writers | $4–20/mo |
| Word / Google Docs | Track changes, comments, styles, inline images, universal familiarity | No story model whatsoever | — |

### 2.2 Unfilled gaps — the basis for differentiation

1. **Deterministic continuity.** Every competitor relies on injecting context into a prompt and trusting the model. Novel OS already runs nine verifiable checks for free and instantly. No rival has an equivalent.
2. **Pipeline provenance.** Sudowrite and NovelCrafter are one-shot generators. Outline → Draft → Revised → Validated → Final with immutable history is a category-defining structure.
3. **Reliability as a wedge.** NovelCrafter's loudest user complaints are data loss and context blindness — exactly what Novel OS's atomic-write, state-first architecture is designed to prevent.
4. **Consequence preview.** Edit a paragraph, see the story ripple before accepting. Exists in no shipping product.
5. **Zero marginal token cost.** NovelCrafter offers BYO-keys; nobody offers "run it on your existing Claude subscription." Novel OS already supports this via the Claude Code CLI provider.
6. **No product spans all three layers.** Scrivener has structure without AI. Sudowrite has AI without structure. Atticus has export without either.

### 2.3 Positioning

> Scrivener's structure, Word's editing surface, and an agent pipeline with a world model that knows when an edit breaks the story.

The strategic ordering follows from this: build the moat first, then reach parity. Competing on Scrivener's turf before the differentiators exist would mean months of building things Scrivener already does well.

---

## 3. Decomposition

Novel OS as a commercial product is too large for one spec. It decomposes into seven sub-projects, each of which gets its own spec and implementation plan.

| # | Sub-project | Purpose |
|---|---|---|
| SP-0 | Foundations & rails | Google Sans typography, media storage, document-tree engine migration, multi-tenant data model |
| SP-1 | Rich-text writing surface | ProseMirror migration; the substrate for track changes, inline images, anchored comments, export fidelity |
| SP-2 | The moat | Continuity surfacing, Codex world model, consequence preview, pipeline provenance |
| SP-3 | Studio parity | Binder, corkboard, outliner, collections, targets, statistics, research board |
| SP-4 | Word-class editing | Track changes, text-anchored comments, styles, spelling and grammar |
| SP-5 | Images & media | Codex portraits, moodboard, inline manuscript images, AI generation |
| SP-6 | Publishing | Compile engine producing DOCX, EPUB, PDF, HTML with automatic front-matter |
| SP-7 | Commercialization | Auth, billing, onboarding, pricing, marketing site |

---

## 4. Architectural decisions

### 4.1 Storage model — hybrid file + database

The per-project `story_state.json`, manuscript files, and feedback artifacts remain the **canonical source of truth**. Postgres holds only tenancy concerns: users, workspaces, project ownership, sessions, billing, and the existing snapshot/comment metadata.

*Rationale.* The engine and CLI continue to work untouched, the "state first, everything else regenerable" design principle survives, and *your novel is a folder you can walk away with* becomes a marketable answer to NovelCrafter's cloud lock-in and reported data loss. Hosted deployments give each tenant a namespaced volume.

*Accepted cost.* Concurrent multi-writer editing on one project is not supported by file-level locking alone. Collaboration is therefore scoped as single-writer with personas (author/editor/beta) rather than simultaneous editing. Revisit only if real-time co-authoring becomes a requirement.

### 4.2 Text representation — ProseMirror canonical, markdown projected

Final text is stored as ProseMirror JSON. A markdown projection is generated on demand for agent consumption.

*Consequence:* **all five agent prompts remain unchanged.** Drafts and AI revisions stay immutable markdown provenance; only Final becomes rich text. Existing `.md` finals migrate through a markdown → ProseMirror JSON converter with a golden-file test per fixture.

### 4.3 Document tree

`StoryState.chapters` (flat `int → ChapterState`) becomes an ordered tree of typed nodes: `part` / `chapter` / `scene` / `folder`. Scenes become the atomic writable unit. Existing flat projects migrate to `part:Manuscript → chapter → single scene`, gated behind a migration test before any UI is built on it.

### 4.4 Images and media

Object storage — local filesystem in development, S3-compatible in production. Image records live in Postgres and are referenced by URL from both ProseMirror nodes and Codex entries. AI generation goes through a new `core/image_client.py` mirroring the provider-agnostic pattern of `llm_client.py`, preserving the BYO-key story.

### 4.5 Typography

| Token | Today | Target |
|---|---|---|
| `--font-sans` | Hanken Grotesk Variable | **Google Sans Flex** |
| `--font-display` | Fraunces Variable | **Google Sans Flex** (weight 600) |
| `--font-mono` | (none declared) | **Google Sans Code** |
| `--font-prose` | Newsreader | **user-controlled**, default Google Sans Flex |

Google Sans proper is under a Google-restricted licence and cannot be used. **Google Sans Flex** and **Google Sans Code** are released under the SIL Open Font License and are free for commercial use with no attribution required. Both are self-hosted via `@fontsource-variable/google-sans-flex` and `@fontsource-variable/google-sans-code`.

The manuscript canvas gets a reader font control offering Google Sans Flex (default), Newsreader (serif), and Google Sans Code (mono), persisted per user — matching the reading-preference affordance Scrivener and Ulysses provide.

*Knock-on:* the drop-cap and `hr::before` ornament in `.prose-manuscript` currently key off `--font-display`; they must be re-tuned for Google Sans Flex's metrics rather than inheriting Fraunces' proportions.

---

## 5. Phase order

Moat-first. Each phase ships working, tested, committed software.

```
P0  Rails          Google Sans typography + reader font picker · media storage
                   · document-tree migration · tenancy data model
P1  Surface        ProseMirror migration · markdown projection · inline images
                   · text-anchored comments
P2  Moat A         Continuity surfacing · Codex world model · Codex portraits
P3  Moat B         Consequence preview · pipeline provenance · review workflow
P4  Studio         Binder · corkboard · outliner · collections · targets & stats
                   · research moodboard
P5  Word parity    Track changes / suggest mode · styles · spelling & grammar
                   · AI image generation
P6  Publishing     Compile engine → DOCX / EPUB / PDF / HTML
P7  Commercial     Auth · billing · onboarding · pricing · marketing site
```

**P2 is the highest value-per-hour work in the plan.** `continuity_engine.py` runs nine checks today whose findings reach only the CLI and the Guardian's prompt — the single strongest differentiator is currently invisible in the product. Exposing it is cheap.

---

## 6. Cross-cutting standards

- Engine changes are additive and migrated; agent logic and prompts are never rewritten to accommodate the UI.
- Writes are atomic (temp + rename) and guarded against path traversal.
- Drafts and AI revisions are immutable provenance. Only Final and human-confirmed metadata are user-mutable. Every AI output has a review surface — a diff with accept/reject, never a silent overwrite.
- Agents never run inline in an HTTP request; they go through the job registry.
- All motion respects `prefers-reduced-motion`. Fonts and assets are self-hosted.
- Every phase closes green: `pytest`, `vitest`, `npm run build`, `npm run lint`.
- No chart libraries; analytics visuals are in-house SVG.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Document-tree migration (P0)** — riskiest engine change | Golden-file migration tests before any UI depends on the tree |
| **ProseMirror migration (P1)** — rewrites both editors | Markdown projection keeps agents unchanged; per-fixture round-trip tests |
| **Consequence accuracy (P3)** | Ground in deterministic continuity checks first; label AI-inferred ripple as "predicted" |
| **Export fidelity (P6)** | Lean on proven libraries; validate EPUB against epubcheck |
| **Scope** — eight phases is a long arc | Each phase is independently shippable; reprioritize at any boundary |
| **Single-writer constraint (§4.1)** | Accepted deliberately; collaboration ships as personas, not simultaneous editing |

---

## 8. Definition of done

Scrivener-grade structure (binder, corkboard, outliner, collections, snapshots, targets, compile) and Word-grade editing (track changes, styles, anchored comments, inline images), plus the three things no competitor has: live agent runs with pipeline provenance, a deterministic continuity engine surfaced in the product, and consequence preview. Sold as a hosted product with BYO-key and subscription-CLI modes, on Google Sans throughout, accessible and fast in light and dark.
