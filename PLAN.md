# Novel OS End-to-End Plan

**Last updated:** 2026-07-31
**Design spec:** [`docs/superpowers/specs/2026-07-31-novel-os-commercial-product-design.md`](docs/superpowers/specs/2026-07-31-novel-os-commercial-product-design.md)
**Goal:** Turn Novel OS from a local multi-agent CLI + dashboard into a commercial product.

> **Positioning.** Scrivener's structure, Word's editing surface, and an agent pipeline with a world model that knows when an edit breaks the story.

---

## Status board

| Phase | Name | State |
|---|---|---|
| P0 | Rails typography, media, document tree, tenancy | ✅ **Complete** |
| P1 | Surface ProseMirror, inline images, anchored comments | ✅ Shipped |
| UI | Flagship glass (Approach B, SF Pro) | ✅ Shipped |
| Assets | Lucide icons + Novel OS mark (self-hosted) | ✅ Staged |
| UX | Library cards + Studio Settings + first-run | ✅ Shipped |
| P2 | Moat A continuity surfacing, Codex, portraits | ◐ Health + Codex UI + Guardian injection + **context packs** + **R4 relationship checks** all shipped (11 checks in `ALL_CHECKS`); **Codex auto-extract proposals** is the only item left |
| P3 | Moat B consequence preview, provenance, review | ◐ Preview + provenance + review + comment personas |
| P4 | Studio binder, corkboard, outliner, research | ◐ Binder + corkboard + outliner + research + **⌘K search** + **Collections MVP**; semantic collections later |
| P5 | Word parity track changes, styles, AI images | ◐ **Track changes shipped** (suggest mode, accept/reject, reject-all projection); styles / spellcheck / AI images not started |
| P6 | Publishing DOCX / EPUB / PDF / HTML | ☐ Not started |
| P7 | Commercial auth, billing, onboarding, marketing | ☐ Not started |

**Storage + layer architecture:** [`docs/superpowers/plans/2026-08-08-full-stack-architecture-and-buildout.md`](docs/superpowers/plans/2026-08-08-full-stack-architecture-and-buildout.md)
— where every byte lives, what belongs in the system, and what deliberately does not.

**State as of 2026-08-08 (`27b7865`):** the P1–P4 buildout is committed and all four
suites are green (pytest 226 · vitest 13 · `npm run build` · `eslint`). Next up is
P5, gated on the note in §6 of the architecture doc: styles must land before P6.

---

## Competitive context

| Tool | Strength | Fatal gap |
|---|---|---|
| Scrivener | Binder, corkboard, outliner, snapshots, collections, compile, writing history | Zero AI; desktop-bound |
| Atticus | Formatting and export; 17 templates; publish-ready PDF/EPUB | No planning features at all |
| Dabble | Cleanest cloud drafting; Plot Grid for arcs and subplots | Shallow worldbuilding, thin AI |
| Plottr | Timeline and template outlining | Planning only export elsewhere to write |
| Campfire | Relationship webs, interactive timeline, conlang dictionary | Modules sold separately; weak editor |
| Sudowrite | Best raw prose (Muse); Describe/Dialogue tools | No persistent memory across sessions |
| NovelCrafter | Codex with auto context injection, scene beats, BYO keys | Setup friction; chat can't see scene content; reported data loss; rigid structure |
| Word / Docs | Track changes, comments, styles, images | No story model |

**The six unfilled gaps Novel OS targets:** deterministic continuity checking · pipeline provenance · reliability as a wedge · consequence preview · zero marginal token cost via the Claude Code CLI · spanning structure + editing + AI in one product.

---

## P0 Rails

Foundations everything else sits on. Two of these are the explicitly requested typography and media work.

### P0.1 Google Sans typography ✅
- Add `@fontsource-variable/google-sans-flex` and `@fontsource-variable/google-sans-code`; drop `@fontsource-variable/hanken-grotesk` and `@fontsource-variable/fraunces`. Keep `@fontsource/newsreader` it becomes a reader option, not a default.
- Retarget `@theme` tokens in `web/src/index.css`: `--font-sans` and `--font-display` → Google Sans Flex; add `--font-mono` → Google Sans Code.
- Re-tune `.prose-manuscript`'s drop-cap (`::first-letter`) and `hr::before` ornament for Google Sans Flex metrics they are currently proportioned for Fraunces.
- Point `MarkdownEditor.tsx`'s CodeMirror `.cm-scroller` / content theme at the new prose token.
- Verify contrast still passes WCAG AA against the audited ink/paper palette; Google Sans Flex has a different x-height than Hanken Grotesk.

### P0.2 Reader font picker ✅
- Introduce `--font-prose` as a user-controlled token with three options: Google Sans Flex (default), Newsreader (serif), Google Sans Code (mono).
- Persist per user alongside existing reading controls; apply to the manuscript canvas only, never to chrome.
- Extend the existing reading-controls surface in `ChapterView.tsx`; add a Vitest case asserting the token switches and persists.

### P0.3 Media storage ✅
- Storage abstraction: local filesystem in dev, S3-compatible in prod.
- Image records table; upload endpoint with type/size validation and path-traversal guards.
- Serve with content-addressed URLs so images are cacheable and de-duplicated.

### P0.4 Document tree migration ✅
- Ordered typed nodes (`part` / `chapter` / `scene` / `folder`) in `core/document_tree.py`, stored flat with `parent_id` + `order` so reorders are local edits rather than rewrites.
- Flat `chapters{int → ChapterState}` migrates to `part:Manuscript → chapter → scenes` on load; `save_state()` re-syncs so the two representations cannot drift. User renames and reordering are preserved only engine-owned facts (word count, POV, status) are mirrored.
- **Golden-file migration test** (`tests/golden/binder_migration.json`) pins the migrated shape; migration ids are deterministic (`ch-001-s01`) so the file is readable and stable.
- Tree read API at `GET /api/projects/{id}/binder`; flat chapter endpoints untouched.
- **Deferred:** scenes are modelled but the writing path stays chapter-level. Making a scene the atomic writable unit is a separate change that lands with the binder UI in P4 doing it here would have broken the agent pipeline, which writes `chapter_NNN_*.md`.

### P0.5 Tenancy data model ✅
- `Workspace`, `User`, `Membership` (owner > editor > viewer), `ProjectOwnership`, `AuthSession` tables in `api/db.py`; helpers in `api/tenancy.py`. Per-project files stay canonical (see spec §4.1) these tables record *who may see* a project, never the story.
- `ProjectService` takes an optional workspace. The default workspace maps to the flat `<root>/<project>` layout, so **an existing local install needs no migration and no moved folders**; other workspaces are namespaced under `ws-<slug>/`.
- Project ids are pattern-validated before any path is built, so `..`, separators, absolute paths and drive letters cannot escape a workspace. A traversing id is reported as 404, indistinguishable from a missing project.
- Creating a project claims it for the caller's workspace, so ownership is recorded rather than inferred from where a folder happens to sit.
- **Deferred:** Postgres itself. The schema is SQLModel, which runs on SQLite today and Postgres by changing the URL adopting Postgres before there is a hosted deployment would add an ops dependency with no consumer. No auth UI; P7 adds sign-in on these tables.

**Done when:** ✅ the app is entirely on Google Sans with a working reader font picker, images upload and serve, the tree migration passes golden tests, and tenancy schema exists. All suites green.

---

## P1 Surface

The ProseMirror migration. Load-bearing for track changes, inline images, anchored comments, and export fidelity.

- Replace CodeMirror with a TipTap/ProseMirror editor in `MarkdownEditor.tsx` and `FinalEditor.tsx`.
- ProseMirror JSON becomes canonical for Final; generate a **markdown projection** on demand for agents **all five agent prompts stay unchanged.**
- Markdown → ProseMirror converter for existing `.md` finals, with a round-trip golden test per fixture.
- **Inline manuscript images**: image nodes with alt text and captions, sized and positioned, surviving into export.
- **Text-anchored comments**: migrate comments from line anchors to ProseMirror positions that survive edits. Backfill existing comments by best-effort position mapping, flagging any that can't be resolved.
- Drafts and AI revisions stay immutable markdown provenance; only Final is rich text.

**Done when:** Final is rich text, images embed inline, comments survive edits, agents are unaffected, and every existing manuscript migrated cleanly.

---

## P2 Moat A

**Highest value-per-hour work in the plan.** `continuity_engine.py` runs nine checks today whose findings reach only the CLI and the Guardian's prompt. The single strongest differentiator is currently invisible in the product.

### P2.1 Continuity surfacing
- Continuity panel in the Inspector: live findings by severity (critical / warning / info), each linking to the chapter or thread that triggered it.
- Project-level continuity health on the dashboard the "nobody else has this" screen.
- Per-chapter badges driven by real check results, not status strings.
- Run checks on demand and after every state mutation; they are free and instant, so there is no reason to batch them.

### P2.2 Codex world model
- Generalize characters into typed entries: `character`, `location`, `worldbuilding`, `item`. Structured fields, freeform notes, links to scenes.
- Guardian validates prose against the Codex; entities auto-extract from prose as *proposals* requiring human confirmation.
- Codex database views with filtering; wire into ⌘K and sidebar search.

### P2.3 Codex portraits
- Attach reference images to Codex entries character portraits, location shots, item sketches.
- Surface in Cast/Codex views and the Inspector. Uses P0.3 media storage.

**Done when:** continuity findings are visible and actionable in the UI, the Codex holds typed entries with images, and the Guardian validates against it.

---

## P3 Moat B

### P3.1 Consequence preview
Select a paragraph → prompt → Scribe rewrites → Guardian computes the story ripple → preview before accepting. Exists in no shipping product.
- Ground the ripple in deterministic continuity checks first; label AI-inferred consequences as **predicted**, never as fact.
- Accept applies to Final *and* world state in one transaction.

### P3.2 Pipeline provenance
- Every artifact records `produced_by` (agent + model) and `reviewed_by` / `reviewed_at`.
- Flow ribbon: Outline → Draft → Revised → Validated → Final, each node viewable and runnable.
- Semantic diff between stages "what changed in the story," not just what changed in the text.

### P3.3 Review workflow
- Three-state lifecycle on every writable unit: `proposed` → `in_review` → `final`.
- Every AI output gets a review surface with accept/reject. Agents never write Final directly.
- Comment personas (author / editor / beta) single-writer collaboration, per spec §4.1.
- **Shipped MVP:** `POST …/stages/{draft|revised}/review` (accept → stamp + promote Final; reject → leave Final); promote gated unless reviewed or `force=true`; Accept/Reject on ProvenancePane; pipeline “Needs review” cue.

**Done when:** the AI-proposes/human-disposes lifecycle is enforced end to end and consequence preview works on a real manuscript.

---

## P4 Studio

Scrivener parity, now that the differentiators exist.

- **Binder** tree with status/label dots, drag-reorder, split/merge, search. Reorder triggers continuity re-check.
  - **Shipped MVP:** `POST …/binder/move`; ChapterView binder with drag handle + ↑/↓; chapter numbers stable.
- **Corkboard** index cards with synopses, drag to restructure. Architect generates and refreshes synopses.
  - **Shipped MVP:** `PATCH …/binder/{node_id}` for synopsis; Corkboard drag + ↑/↓ + inline edit.
  - **Shipped:** `POST …/chapters/{n}/synopsis/refresh` (Architect, heuristic fallback); Corkboard “Refresh with Architect”.
- **Outliner** sortable metadata table with AI-computed columns: tension, emotional intensity, pacing.
  - **Shipped MVP:** `POST …/outliner/metrics/refresh` (Style Curator heuristics → binder `derived`); Outliner Tension / Emotion / Pace columns + sort + Refresh metrics.
- **Collections & search** saved metadata searches; semantic queries over the world model.
- **Targets & statistics** project and session word targets, progress rings, reading time, word frequency and echo detection via Style Curator.
  - **Shipped MVP:** project `target_word_count` + `session_word_target`; dashboard Writing Targets rings + edit; library cards use word progress; session baseline in localStorage.
  - **Shipped:** `GET …/statistics` (deterministic Style Curator: reading time, top words, echoes); dashboard Manuscript statistics panel.
- **Research moodboard** per-project workspace for images, web clips, PDFs, tagged notes. Split-screen alongside the manuscript.
  - **Shipped MVP:** `/projects/:id/research` board; upload/drop `kind=research` images; caption edit via `PATCH …/media/{id}`; links from dashboard + binder.

---

## P5 Word parity

- **Track changes / suggest mode** color-coded edits, accept/reject per change, author attribution. AI suggestions render as in-place marks.
  - **Shipped:** `suggestionInsert` / `suggestionDelete` marks; suggest mode turns typing into proposals and deletion into struck text; per-change and bulk accept/reject in `SuggestionsPanel`; resolution is a pure JSON transform (`web/src/lib/trackChanges.ts`) so it is exactly testable and undoable.
  - **Enforced at the storage layer, not just the UI:** `api/richtext.py` projects the *reject-all* view, so a pending suggestion is never in the markdown agents read or the file on disk. `save_final_doc` applies house style to text nodes instead of re-parsing markdown, which would have wiped every suggestion on the first save.
  - **Still to do:** routing agent revisions in as suggestions rather than into the `revised` stage, and per-change attribution once P7 auth supplies real identities.
- **Styles system** named styles driving compile output (Scrivener compile parity).
- **Spelling & grammar** with a per-project dictionary so invented names and terms stop being flagged.
- **AI image generation** character portraits, cover art, scene illustrations from story state. New `core/image_client.py` mirroring the provider-agnostic pattern of `llm_client.py`, preserving BYO-key.

---

## P6 Publishing

- Compile engine walking the document tree.
- **DOCX / EPUB / PDF / HTML** with automatic front-matter, blurb, and chapter titles drawn from state.
- Inline images and styles carry through with fidelity.
- Export presets; validate EPUB against epubcheck.

---

## P7 Commercial

- **Auth** sign-up, sign-in, sessions, password reset, on the P0.5 schema.
- **Billing** subscription tiers. Two AI modes: BYO-key and subscription-CLI (zero marginal token cost no competitor offers this).
- **Onboarding** templates, sample project, genre-aware scaffolding from the Architect. Directly targets NovelCrafter's documented setup friction.
- **Pricing** positioned against NovelCrafter ($4–20/mo) and Sudowrite ($29/mo).
- **Marketing site** leading with the three things nobody else has: deterministic continuity, pipeline provenance, consequence preview.

---

## Cross-cutting standards

- Engine changes are additive and migrated. Agent logic and prompts are never rewritten to accommodate the UI.
- Writes are atomic (temp + rename), guarded against path traversal.
- Drafts and AI revisions are immutable provenance. Only Final and human-confirmed metadata are user-mutable.
- Every AI output has a review surface a diff with accept/reject, never a silent overwrite.
- Agents never run inline in an HTTP request; they go through the job registry.
- All motion respects `prefers-reduced-motion`. Fonts and assets self-hosted.
- No chart libraries analytics visuals are in-house SVG.
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

- [Best Book Writing Software (2026) Reedsy](https://reedsy.com/blog/guide/book-writing-software/)
- [Scrivener vs Atticus vs Dabble vs Ulysses (2026) Laterpress](https://www.laterpress.com/comparisons/writing-software-compared/)
- [Introducing Scrivener 3 Literature & Latte](https://www.literatureandlatte.com/introducing-scrivener-3)
- [Novelcrafter vs Sudowrite (2026) Nextool](https://nextool.ai/compare/novelcrafter-vs-sudowrite/)
- [Novelcrafter Review Kindlepreneur](https://kindlepreneur.com/novelcrafter-review/)
- [Novelcrafter feedback board](https://feedback.novelcrafter.com/)
- [Best AI Novel Writing Tools 2026 epos-ai](https://epos-ai.ch/en/blog/best-ai-novel-writing-tools-2026.html)
- [Google's brand font is now free for anyone to use Creative Bloq](https://www.creativebloq.com/design/fonts-typography/googles-iconic-brand-font-is-now-free-for-anyone-to-use)
- [Google Sans Flex Google Fonts](https://fonts.google.com/specimen/Google+Sans)
