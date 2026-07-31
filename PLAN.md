# Novel OS — End-to-End Plan

**Last updated:** 2026-07-31
**Design spec:** [`docs/superpowers/specs/2026-07-31-novel-os-commercial-product-design.md`](docs/superpowers/specs/2026-07-31-novel-os-commercial-product-design.md)
**Goal:** Turn Novel OS from a local multi-agent CLI + dashboard into a commercial product.

> **Positioning.** Scrivener's structure, Word's editing surface, and an agent pipeline with a world model that knows when an edit breaks the story.

---

## Status board

| Phase | Name | State |
|---|---|---|
| P0 | Rails — typography, media, document tree, tenancy | ◐ In progress — P0.1–P0.4 ✅ · P0.5 ☐ |
| P1 | Surface — ProseMirror, inline images, anchored comments | ☐ Not started |
| P2 | Moat A — continuity surfacing, Codex, portraits | ☐ Not started |
| P3 | Moat B — consequence preview, provenance, review | ☐ Not started |
| P4 | Studio — binder, corkboard, outliner, research | ☐ Not started |
| P5 | Word parity — track changes, styles, AI images | ☐ Not started |
| P6 | Publishing — DOCX / EPUB / PDF / HTML | ☐ Not started |
| P7 | Commercial — auth, billing, onboarding, marketing | ☐ Not started |

**Pre-flight:** the working tree carries an uncommitted repo-wide em-dash strip (35 files, 286/286). Commit or discard before P0 starts.

---

## Competitive context

| Tool | Strength | Fatal gap |
|---|---|---|
| Scrivener | Binder, corkboard, outliner, snapshots, collections, compile, writing history | Zero AI; desktop-bound |
| Atticus | Formatting and export; 17 templates; publish-ready PDF/EPUB | No planning features at all |
| Dabble | Cleanest cloud drafting; Plot Grid for arcs and subplots | Shallow worldbuilding, thin AI |
| Plottr | Timeline and template outlining | Planning only — export elsewhere to write |
| Campfire | Relationship webs, interactive timeline, conlang dictionary | Modules sold separately; weak editor |
| Sudowrite | Best raw prose (Muse); Describe/Dialogue tools | No persistent memory across sessions |
| NovelCrafter | Codex with auto context injection, scene beats, BYO keys | Setup friction; chat can't see scene content; reported data loss; rigid structure |
| Word / Docs | Track changes, comments, styles, images | No story model |

**The six unfilled gaps Novel OS targets:** deterministic continuity checking · pipeline provenance · reliability as a wedge · consequence preview · zero marginal token cost via the Claude Code CLI · spanning structure + editing + AI in one product.

---

## P0 — Rails

Foundations everything else sits on. Two of these are the explicitly requested typography and media work.

### P0.1 Google Sans typography
- Add `@fontsource-variable/google-sans-flex` and `@fontsource-variable/google-sans-code`; drop `@fontsource-variable/hanken-grotesk` and `@fontsource-variable/fraunces`. Keep `@fontsource/newsreader` — it becomes a reader option, not a default.
- Retarget `@theme` tokens in `web/src/index.css`: `--font-sans` and `--font-display` → Google Sans Flex; add `--font-mono` → Google Sans Code.
- Re-tune `.prose-manuscript`'s drop-cap (`::first-letter`) and `hr::before` ornament for Google Sans Flex metrics — they are currently proportioned for Fraunces.
- Point `MarkdownEditor.tsx`'s CodeMirror `.cm-scroller` / content theme at the new prose token.
- Verify contrast still passes WCAG AA against the audited ink/paper palette; Google Sans Flex has a different x-height than Hanken Grotesk.

### P0.2 Reader font picker
- Introduce `--font-prose` as a user-controlled token with three options: Google Sans Flex (default), Newsreader (serif), Google Sans Code (mono).
- Persist per user alongside existing reading controls; apply to the manuscript canvas only, never to chrome.
- Extend the existing reading-controls surface in `ChapterView.tsx`; add a Vitest case asserting the token switches and persists.

### P0.3 Media storage ✅
- Storage abstraction: local filesystem in dev, S3-compatible in prod.
- Image records table; upload endpoint with type/size validation and path-traversal guards.
- Serve with content-addressed URLs so images are cacheable and de-duplicated.

### P0.4 Document tree migration ✅
- Ordered typed nodes (`part` / `chapter` / `scene` / `folder`) in `core/document_tree.py`, stored flat with `parent_id` + `order` so reorders are local edits rather than rewrites.
- Flat `chapters{int → ChapterState}` migrates to `part:Manuscript → chapter → scenes` on load; `save_state()` re-syncs so the two representations cannot drift. User renames and reordering are preserved — only engine-owned facts (word count, POV, status) are mirrored.
- **Golden-file migration test** (`tests/golden/binder_migration.json`) pins the migrated shape; migration ids are deterministic (`ch-001-s01`) so the file is readable and stable.
- Tree read API at `GET /api/projects/{id}/binder`; flat chapter endpoints untouched.
- **Deferred:** scenes are modelled but the writing path stays chapter-level. Making a scene the atomic writable unit is a separate change that lands with the binder UI in P4 — doing it here would have broken the agent pipeline, which writes `chapter_NNN_*.md`.

### P0.5 Tenancy data model
- Postgres for users, workspaces, project ownership, sessions. Per-project files stay canonical (see spec §4.1).
- Namespaced per-tenant volumes; no cross-tenant path reachability.
- No auth UI yet — P0 lays the schema so P7 doesn't force a rewrite.

**Done when:** the app is entirely on Google Sans with a working reader font picker, images upload and serve, the tree migration passes golden tests, and tenancy schema exists. All suites green.

---

## P1 — Surface

The ProseMirror migration. Load-bearing for track changes, inline images, anchored comments, and export fidelity.

- Replace CodeMirror with a TipTap/ProseMirror editor in `MarkdownEditor.tsx` and `FinalEditor.tsx`.
- ProseMirror JSON becomes canonical for Final; generate a **markdown projection** on demand for agents — **all five agent prompts stay unchanged.**
- Markdown → ProseMirror converter for existing `.md` finals, with a round-trip golden test per fixture.
- **Inline manuscript images**: image nodes with alt text and captions, sized and positioned, surviving into export.
- **Text-anchored comments**: migrate comments from line anchors to ProseMirror positions that survive edits. Backfill existing comments by best-effort position mapping, flagging any that can't be resolved.
- Drafts and AI revisions stay immutable markdown provenance; only Final is rich text.

**Done when:** Final is rich text, images embed inline, comments survive edits, agents are unaffected, and every existing manuscript migrated cleanly.

---

## P2 — Moat A

**Highest value-per-hour work in the plan.** `continuity_engine.py` runs nine checks today whose findings reach only the CLI and the Guardian's prompt. The single strongest differentiator is currently invisible in the product.

### P2.1 Continuity surfacing
- Continuity panel in the Inspector: live findings by severity (critical / warning / info), each linking to the chapter or thread that triggered it.
- Project-level continuity health on the dashboard — the "nobody else has this" screen.
- Per-chapter badges driven by real check results, not status strings.
- Run checks on demand and after every state mutation; they are free and instant, so there is no reason to batch them.

### P2.2 Codex world model
- Generalize characters into typed entries: `character`, `location`, `worldbuilding`, `item`. Structured fields, freeform notes, links to scenes.
- Guardian validates prose against the Codex; entities auto-extract from prose as *proposals* requiring human confirmation.
- Codex database views with filtering; wire into ⌘K and sidebar search.

### P2.3 Codex portraits
- Attach reference images to Codex entries — character portraits, location shots, item sketches.
- Surface in Cast/Codex views and the Inspector. Uses P0.3 media storage.

**Done when:** continuity findings are visible and actionable in the UI, the Codex holds typed entries with images, and the Guardian validates against it.

---

## P3 — Moat B

### P3.1 Consequence preview
Select a paragraph → prompt → Scribe rewrites → Guardian computes the story ripple → preview before accepting. Exists in no shipping product.
- Ground the ripple in deterministic continuity checks first; label AI-inferred consequences as **predicted**, never as fact.
- Accept applies to Final *and* world state in one transaction.

### P3.2 Pipeline provenance
- Every artifact records `produced_by` (agent + model) and `reviewed_by` / `reviewed_at`.
- Flow ribbon: Outline → Draft → Revised → Validated → Final, each node viewable and runnable.
- Semantic diff between stages — "what changed in the story," not just what changed in the text.

### P3.3 Review workflow
- Three-state lifecycle on every writable unit: `proposed` → `in_review` → `final`.
- Every AI output gets a review surface with accept/reject. Agents never write Final directly.
- Comment personas (author / editor / beta) — single-writer collaboration, per spec §4.1.

**Done when:** the AI-proposes/human-disposes lifecycle is enforced end to end and consequence preview works on a real manuscript.

---

## P4 — Studio

Scrivener parity, now that the differentiators exist.

- **Binder** — tree with status/label dots, drag-reorder, split/merge, search. Reorder triggers continuity re-check.
- **Corkboard** — index cards with synopses, drag to restructure. Architect generates and refreshes synopses.
- **Outliner** — sortable metadata table with AI-computed columns: tension, emotional intensity, pacing.
- **Collections & search** — saved metadata searches; semantic queries over the world model.
- **Targets & statistics** — project and session word targets, progress rings, reading time, word frequency and echo detection via Style Curator.
- **Research moodboard** — per-project workspace for images, web clips, PDFs, tagged notes. Split-screen alongside the manuscript.

---

## P5 — Word parity

- **Track changes / suggest mode** — color-coded edits, accept/reject per change, author attribution. AI suggestions render as in-place marks.
- **Styles system** — named styles driving compile output (Scrivener compile parity).
- **Spelling & grammar** — with a per-project dictionary so invented names and terms stop being flagged.
- **AI image generation** — character portraits, cover art, scene illustrations from story state. New `core/image_client.py` mirroring the provider-agnostic pattern of `llm_client.py`, preserving BYO-key.

---

## P6 — Publishing

- Compile engine walking the document tree.
- **DOCX / EPUB / PDF / HTML** with automatic front-matter, blurb, and chapter titles drawn from state.
- Inline images and styles carry through with fidelity.
- Export presets; validate EPUB against epubcheck.

---

## P7 — Commercial

- **Auth** — sign-up, sign-in, sessions, password reset, on the P0.5 schema.
- **Billing** — subscription tiers. Two AI modes: BYO-key and subscription-CLI (zero marginal token cost — no competitor offers this).
- **Onboarding** — templates, sample project, genre-aware scaffolding from the Architect. Directly targets NovelCrafter's documented setup friction.
- **Pricing** — positioned against NovelCrafter ($4–20/mo) and Sudowrite ($29/mo).
- **Marketing site** — leading with the three things nobody else has: deterministic continuity, pipeline provenance, consequence preview.

---

## Cross-cutting standards

- Engine changes are additive and migrated. Agent logic and prompts are never rewritten to accommodate the UI.
- Writes are atomic (temp + rename), guarded against path traversal.
- Drafts and AI revisions are immutable provenance. Only Final and human-confirmed metadata are user-mutable.
- Every AI output has a review surface — a diff with accept/reject, never a silent overwrite.
- Agents never run inline in an HTTP request; they go through the job registry.
- All motion respects `prefers-reduced-motion`. Fonts and assets self-hosted.
- No chart libraries — analytics visuals are in-house SVG.
- Every phase closes green: `pytest`, `vitest`, `npm run build`, `npm run lint`.

---

## Risks

| Risk | Mitigation |
|---|---|
| Document-tree migration (P0.4) | Golden-file tests before any UI depends on the tree |
| ProseMirror migration (P1) | Markdown projection keeps agents unchanged; per-fixture round-trip tests |
| Consequence accuracy (P3.1) | Ground in deterministic checks; label AI inference as predicted |
| Export fidelity (P6) | Proven libraries; validate against epubcheck |
| Eight phases is a long arc | Each phase independently shippable; reprioritize at any boundary |
| Single-writer constraint | Accepted deliberately; collaboration ships as personas |

---

## Sources

- [Best Book Writing Software (2026) — Reedsy](https://reedsy.com/blog/guide/book-writing-software/)
- [Scrivener vs Atticus vs Dabble vs Ulysses (2026) — Laterpress](https://www.laterpress.com/comparisons/writing-software-compared/)
- [Introducing Scrivener 3 — Literature & Latte](https://www.literatureandlatte.com/introducing-scrivener-3)
- [Novelcrafter vs Sudowrite (2026) — Nextool](https://nextool.ai/compare/novelcrafter-vs-sudowrite/)
- [Novelcrafter Review — Kindlepreneur](https://kindlepreneur.com/novelcrafter-review/)
- [Novelcrafter feedback board](https://feedback.novelcrafter.com/)
- [Best AI Novel Writing Tools 2026 — epos-ai](https://epos-ai.ch/en/blog/best-ai-novel-writing-tools-2026.html)
- [Google's brand font is now free for anyone to use — Creative Bloq](https://www.creativebloq.com/design/fonts-typography/googles-iconic-brand-font-is-now-free-for-anyone-to-use)
- [Google Sans Flex — Google Fonts](https://fonts.google.com/specimen/Google+Sans)
