# Novel OS — AI Writing Studio: Engine + UI Roadmap (End-to-End)

**Date:** 2026-06-10
**Status:** Proposed vision + roadmap (awaiting approval). Absorbs the earlier polish plan (as "Track C") and the pipeline/consequence plan.
**Goal:** Turn Novel OS into a full writing studio with Scrivener-grade structure — **plus** the two things Scrivener can never have: an agent pipeline that writes/revises, and a world model that catches story consequences. This plan covers both the **engine (core/)** and the **UI (web/)**.

---

## 1. Positioning

> **Scrivener manages the lifecycle of a novel. Novel OS manages it *and writes it with you* — with a world model that knows when an edit breaks the story.**

Scrivener = Word + Notion + Trello + research DB for authors (binder, corkboard, outliner, snapshots, metadata, compile). Novel OS should match that studio surface, then beat it on the axes Scrivener has no answer for:

| Novel OS advantage | Scrivener equivalent |
|---|---|
| Agents (Architect/Scribe/Editor/Guardian) generate & revise | none — fully manual |
| World model + Continuity Guardian flags contradictions | none |
| Pipeline flow: Outline→Draft→Revised→Final provenance | manual snapshots |
| AI-derived metadata (tension, emotion, pacing) | manual labels only |
| Consequence preview (story ripple before you accept) | none |
| Semantic collections ("scenes where Lena suspects sabotage") | text/keyword search only |

So: **build the studio, then make every studio feature AI-native.**

## 1.5 The core lifecycle — **AI-computed → human-reviewed → Final**

One principle governs the whole studio: **the AI proposes, the human disposes.** Everything an agent produces is a *proposal* until a human reviews it. The reviewed result is the **Final** — the only human-owned, mutable, canonical artifact. This is universal, not prose-specific:

| Thing | AI computes (proposal) | Human reviews | Final (canonical) |
|---|---|---|---|
| Chapter/scene prose | outline → draft → revised | read, edit, accept/reject | `final.md` |
| Metadata (tension, emotion, pacing, keywords) | suggested values | confirm or override | recorded value |
| Codex entry (character/location/world) | extracted from prose | confirm/correct | saved entry |
| Inline edit (M6) | rewrite + story ripple | accept / tweak / discard | applied to Final + state |

Implications baked into the engine and UI from M0 on:
- A three-state lifecycle on every writable unit: **`proposed` → `in_review` → `final`** (extends today's status enum).
- **Provenance is immutable.** Drafts, AI revisions, and suggestions are kept as read-only history; only Final and human-confirmed metadata are mutable. Nothing is "Final" until a human reviewed it.
- **Every AI output has a review surface** — a diff/accept/reject affordance — not a silent overwrite. Agents never write Final directly.
- Each artifact records `produced_by` (agent/model) and `reviewed_by`/`reviewed_at`, so you always know what's machine-proposed vs human-blessed.

## 2. Scrivener → Novel OS feature map

Each row = a Scrivener capability, the Novel OS engine support it needs, the UI surface, and the AI upgrade that makes ours better.

| Scrivener feature | Engine (core/) | UI (web/) | AI upgrade (the moat) |
|---|---|---|---|
| **Binder** (Parts→Chapters→Scenes, nest, drag-reorder, split/merge) | Document **tree**: ordered nodes (part/chapter/scene); scene = atomic writable unit | Binder tree, drag-drop, split/merge | Reorder triggers continuity re-check; Architect proposes structure |
| **Corkboard** (index cards, synopsis, rearrange) | Per-scene synopsis + order | Corkboard view of scene cards | Architect generates/refreshes synopses; drag = restructure beats |
| **Outliner** (spreadsheet: title/synopsis/status/wc/target/POV/keywords/custom) | Per-node metadata fields | Sortable outliner table | AI-computed columns: tension, emotional intensity, pacing |
| **Character/World/Locations** | **Codex**: typed entries (character/location/worldbuilding), linked to scenes | Codex database views | Guardian uses codex to validate; auto-extract entities from prose |
| **Research** (PDFs, images, web, notes) | Per-project research store + per-node notes | Research folder + split-screen reference | RAG: agents cite research when drafting |
| **Metadata** (labels, status, keywords, custom) | Fields on every node; status enum already exists | Inspector metadata editor; color labels | Keywords auto-tagged; status auto-advances with pipeline |
| **Writing goals/targets** | Project + session targets in state | Progress rings, session tracker | Predicts completion from pace; suggests scene targets |
| **Snapshots** ("Git for writers", compare, restore) | **Snapshot store** per node + version index | Snapshot timeline, side-by-side diff, restore | Pipeline stages auto-snapshot; semantic diff ("what changed in the story") |
| **Revision mode** (color-coded edits) | Diff between snapshots | Inline colored diff | Guardian annotates which edits touched continuity |
| **Split screen** | (read APIs) | Two-pane: scene+notes, draft+outline, etc. | one pane can be the Consequence panel |
| **Search & Collections** (saved metadata searches) | Query layer over tree + codex | Search bar, saved Collections | Semantic queries over the world model |
| **Templates** | Existing `templates/` → tree templates | New-project / new-scene templates | Genre-aware scaffolding from Architect |
| **Compile/Export** (DOCX/PDF/EPUB/MOBI/HTML) | Compile engine walking the tree | Compile dialog with presets | Auto front-matter, blurb, chapter titles from state |
| **Statistics** (wc, reading time, frequency) | Stats over artifacts | Stats panel | Style Curator: word-frequency/echo + readability flags |
| **Focus/Composition, themes, customization** | — | Typewriter/focus mode, light+dark, controls | — |

## 3. The engine, redesigned (core/)

Today `StoryState` is flat: `chapters{int → ChapterState}` (ChapterState already carries a `scenes[]` list, characters, plot_threads, timeline, style_profile). The studio needs five engine upgrades. All are **additive + migrated**, never a rewrite of the agent logic.

1. **Document tree (`binder`).** An ordered tree of nodes: `part` / `chapter` / `scene` (+ `folder` for research). Scenes become the atomic writable unit; a chapter is its ordered scenes; parts group chapters. Operations: create, reorder (drag), move, split, merge. Back-compat: existing flat chapters migrate to `part:Manuscript → chapter → (single scene)`.
2. **Node artifacts + snapshots.** Each writable node has text artifacts (outline/draft/revised/**final**) and a **snapshot history** (`snapshots/<node_id>/<ts>.md` + index with label). The pipeline stages become labeled snapshots; manual snapshots and restore supported. This *is* the "draft → final flow," generalized.
3. **Metadata.** Every node: `status` (To-Do/Draft/Revised/Final), `label` (color), `keywords[]`, `pov`, `target_words`, and custom fields including **AI-derived** `tension`, `emotional_intensity`, `pacing`, `plot_threads[]`, `timeline_day`.
4. **Codex (world model).** Generalize characters into typed entries: `character`, `location`, `worldbuilding`, `item`. Each has structured fields + freeform notes + **links to scenes** (keywords/wiki-links). Continuity Guardian validates prose against the codex.
5. **Targets, stats, research, compile.** Project/session word targets; statistics (counts, reading time, word frequency via Style Curator); a per-project research store; a compile engine that walks the tree to DOCX/EPUB/PDF/Markdown.

Agents are rebound to operate at **scene or chapter** granularity; the continuity engine cross-references the codex + timeline.

## 4. The UI, redesigned (web/)

A story control system. Core shell = **Binder · Editor · Inspector**, with full-surface views one keystroke away.

- **Binder (left):** the document tree with status/label dots, drag-drop, split/merge, search.
- **Editor (center):** manuscript page (Newsreader prose, drop-cap, running header); **focus/typewriter** mode; **split-screen** (draft+outline, scene+notes, prose+Consequence); rich-text + annotations/comments/footnotes; the **Pipeline Flow** ribbon (Outline→Draft→Revised→Validated→**Final**) where each node is viewable/runnable.
- **Inspector (right):** synopsis (corkboard card), **metadata** editor, document notes, **Snapshots** timeline w/ diff+restore, and (Pillar B) the **Consequence panel**.
- **Full views:** **Corkboard** (scene cards), **Outliner** (metadata spreadsheet), **Codex** (character/location/world DB), **Research**, **Collections/Search**, **Targets & Stats**, **Compile**.
- **The two AI pillars woven throughout:** pipeline flow & live runs (agents), and inline prompt → consequence preview.

## 5. End-to-end roadmap (milestones)

Each milestone ships working, tested software (Vitest + `pytest` + build green), committed, verified live. Three tracks interleave: **A = engine, B = product UI, C = frontend craft.**

> **M0 — Foundations**
> *C:* self-host fonts, React Query data layer, ErrorBoundary, a11y baseline, light/dark tokens.
> *A:* design + migrate the **document-tree** model (parts/chapters/scenes) with back-compat for existing flat projects; expose tree read API. **Biggest engine change — do it carefully, with a migration test.**

> **M1 — Binder + Scene editor + Inspector**
> Tree binder (drag-drop, split/merge), scene-level manuscript editor, inspector with synopsis + metadata. *C:* motion + reading depth.

> **M2 — Pipeline Flow + Snapshots + edit/save Final**
> The flow ribbon (provenance), snapshot history (compare/restore), and **promote→edit→save Final** (first write path). Delivers your "drafts separate / flow to final / edit & save final."

> **M3 — Corkboard + Outliner**
> Scene-card corkboard (drag-reorder) and the metadata outliner table; AI-derived columns (tension/emotion) computed by agents.

> **M4 — Codex + Collections/Search**
> Characters/locations/worldbuilding DB with scene links; saved searches & semantic collections over the world model. *C:* ⌘K command palette + keyboard nav.

> **M5 — Run the pipeline live (jobs + SSE)**
> Trigger any stage (plan/write/edit/validate/approve) from the UI; live progress; the flow animates. Off-thread job registry + SSE. *C:* dark mode + real owl mascot + progress rings.

> **M6 — Consequence engine (signature)**
> Scribe **revise-span** + Guardian **ripple/diff**: select a paragraph → prompt → rewrite + story-ripple preview → accept (updates Final + world-state). The moat.

> **M7 — Compile, Targets, Stats, Research**
> Compile to DOCX/EPUB/PDF with auto front-matter; project/session targets + progress; statistics & word-frequency (Style Curator); research store + split-screen reference.

## 6. Recommended sequence & rationale

```
M0 Foundations (FE + tree engine)
  └ M1 Binder/Editor/Inspector  (+motion/reading)
     └ M2 Flow + Snapshots + edit/save Final   ← your explicit asks land here
        └ M3 Corkboard + Outliner
           └ M4 Codex + Collections  (+⌘K)
              └ M5 Run pipeline live (jobs+SSE)  (+dark/mascot)
                 └ M6 Consequence engine  (signature)
                    └ M7 Compile + Targets + Stats + Research
```
M0 is load-bearing (everything sits on the tree model + RQ data layer). M2 is the first milestone that fully satisfies the "draft → final, editable" request. M6 is last because it depends on the tree, snapshots, codex, and live runs.

## 7. Cross-cutting standards
- Additive engine changes with **migration tests**; never break existing flat projects or agent logic.
- Writes are atomic (temp+rename), id/path-traversal guarded; **drafts & AI revisions are immutable provenance** — only Final and metadata are user-mutable.
- Agents never run inline in an HTTP request (job registry + SSE).
- All motion respects `prefers-reduced-motion`; fonts/assets self-hosted; mascot downscaled.
- Every milestone: backend `pytest`, frontend Vitest, `npm run build` green; keep existing assertions intact.

## 8. Risks
- **Tree migration (M0):** the flat→tree change is the riskiest; gate it behind a migration + golden-file tests before building UI on it.
- **Scope:** 8 milestones is a long arc — each is independently shippable; we can stop or reprioritize at any boundary.
- **Consequence accuracy (M6):** start with deterministic continuity-engine checks; label AI-inferred ripple as "predicted."
- **Compile fidelity (M7):** EPUB/DOCX formatting is fiddly — lean on a proven library (research at build time).

## 9. Definition of done (the studio)
Binder/corkboard/outliner, snapshots, codex, collections, targets/stats, compile — at Scrivener parity — **plus** live agent runs, the Outline→Final pipeline flow with editable Final, and the consequence engine. Polished light+dark, motion, ⌘K, real mascot. All green, accessible, fast.
