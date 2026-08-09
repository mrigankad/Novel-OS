# Changelog

All notable changes to Novel OS. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [semantic versioning](https://semver.org/) — pre-1.0, so minor
versions carry features and may change interfaces.

---

## [0.3.0] — 2026-08-08

**Novel OS became a studio.** v0.2.0 was a multi-agent CLI with a dashboard. This
release adds the writing surface, the world model behind it, and a way to get a
finished book out the other end.

### Added — the studio

- **Rich-text manuscript** (ProseMirror/TipTap). Final is a real document with
  inline images and comments anchored to positions that survive edits. Agents
  keep reading a markdown projection, so no agent prompt changed.
- **Track changes.** Suggest mode turns typing into proposals and deleting into
  struck text, with author attribution and per-change or bulk accept/reject.
- **Plan / Write / Revise modes** (`⌘1` `⌘2` `⌘3`). The four pipeline stages are
  now *provenance* — where a paragraph came from — rather than a workflow.
  Write mode collapses both rails and volunteers nothing.
- **One selection bar.** Rewrite · Expand · Comment · Ask, sharing a single
  definition with the right-click menu. Every AI action returns the same
  three-part answer: the proposal, what it breaks, what it might mean.
- **Quick capture** (`⌘.`) — a note filed against the current chapter without
  leaving the page.
- **Binder, corkboard, outliner, research board, collections**, saved searches,
  writing targets, and manuscript statistics.
- **Codex** — typed world entries (character, location, worldbuilding, item)
  with portraits, a relationship chart, and `⌘K` search across all of it.

### Added — the moat

- **Continuity engine grew to 12 deterministic checks**, including relationship
  integrity, since-anachronisms, contradictory bonds, hostile pairs sharing a
  scene, and dead characters reappearing.
- **Stall detector.** Sagging middles decompose into signals the state already
  records; three consecutive chapters that change nothing are reported as a
  reactive protagonist. Shown as a shape-of-the-book strip. No model involved.
- **"This is intentional."** Any finding can be dismissed with a reason,
  persisted and keyed to the fact rather than the wording. The filter lives in
  the engine, so the Guardian stops re-raising it too.
- **Codex auto-extract.** Import a manuscript and the cast is *proposed* from the
  prose — deterministic, instant, and never written without confirmation.
- **Consequence preview.** Rewrite a passage and see the deterministic ripple
  before accepting; AI-inferred effects are labelled `predicted`, never fact.
- **Context packs** replace dump-and-truncate: ranked, budgeted per purpose.

### Added — publishing

- **Compile engine** split into gather and render, so formats are renderers
  rather than new walks of the manuscript.
- **DOCX, EPUB, HTML and Markdown export — with no new dependencies.** Both
  binary formats are ZIP-of-XML and are written directly against the spec.
- **Named styles** drive compile output: change what "Block Quote" means once
  and the whole book follows.

### Added — foundations

- Ordered document tree (parts / chapters / scenes) with a golden-file migration.
- Content-addressed media store; images de-duplicate and cache by SHA-256.
- Workspace / user / membership schema, ready for P7 auth.
- `NOVEL_OS_DB` accepts a Postgres URL; SQLite-only args are applied only to
  SQLite.
- `NOVEL_OS_CORS_ORIGINS` for running the frontend anywhere.

### Fixed

- **Scene breaks were destroyed on save.** The house-style pass collapsed a `---`
  thematic break into `" - "` and ate the newlines around it, welding two scenes
  into one paragraph. The pass now runs per line and skips break lines.
- **Saving a document re-parsed its own markdown**, which would have discarded
  every pending track change on the first save.
- **Continuity checks could report on the wrong chapter.** `run_all` picked each
  check's arity by catching `TypeError`, so a `TypeError` raised *inside* a
  check silently re-ran it against the default chapter.
- Write mode only collapsed the rails when you switched into it, not on load.
- CORS allowed exactly one hardcoded origin.
- 39 lint errors and a broken production build; all four suites now run clean.

### Changed

- Editor is loaded on demand: opening a chapter no longer downloads TipTap
  before anything paints (593 kB → 166 kB for the chapter route).
- README rewritten around the studio, with screenshots from the running app.

### Tests

374 Python · 70 TypeScript · production build and lint clean.

---

## [0.2.0] — 2026-06-10

- **Key-free Claude Code backend** (`claude_cli`) — run the whole pipeline on a
  Claude subscription with no API key and no per-token billing.
- **Setup wizard** (`python core/orchestrator.py setup`) — detects the CLI, any
  provider key, or a local server, runs a live connection test, and writes
  `.env` without clobbering existing settings.
- Providers: Anthropic, OpenAI, Azure, Gemini, plus any OpenAI-compatible
  endpoint (Kimi, Groq, Together, OpenRouter, DeepSeek, Mistral, Fireworks,
  NVIDIA, Ollama, LM Studio).

## [0.1.0] — 2026-05-23

Initial release. Five-agent pipeline (Architect, Scribe, Editor, Continuity
Guardian, Style Curator), persistent `story_state.json`, and the deterministic
continuity engine.

[0.3.0]: https://github.com/mrigankad/Novel-OS/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mrigankad/Novel-OS/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mrigankad/Novel-OS/releases/tag/v0.1.0
