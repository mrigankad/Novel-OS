# Next Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish P1 Surface, then ship P2 Moat A (continuity + Codex) with a self-hosted icon/brand system already staged in-repo.

**Architecture:** Keep agents on markdown provenance; Final stays TipTap/ProseMirror. Continuity findings and Codex entries surface in Inspector + Dashboard. Icons are self-hosted Lucide SVGs via `Icon` / `FEATURE_ICONS`; brand uses `BrandMark` + `favicon.svg`.

**Tech Stack:** FastAPI + SQLModel, React 19 + Vite, TipTap, Motion, Lucide static SVGs (ISC), SF Pro Display.

## Global Constraints

- Proper case only in UI chrome (no CSS `uppercase` labels).
- Manuscript text stays on opaque `.manuscript-page` (no blur under prose).
- SF Pro Display remains UI font; Lucide for icons; do not reintroduce Geist/Inter.
- Agents never write Final directly; never rewrite agent prompts for UI convenience.
- All assets self-hosted; respect `prefers-reduced-motion`.
- Suites green before phase close: `pytest`, `vitest`, `npm run build`.

---

## Assets already staged (this session)

| Path | Purpose |
|---|---|
| `web/src/assets/icons/*.svg` | 41 Lucide icons (v0.525.0, ISC) |
| `web/src/assets/icons/LICENSE-Lucide.txt` | Attribution |
| `web/src/assets/brand/novel-os-mark.svg` | Owl brand mark (violet `#6867ea`) |
| `web/public/favicon.svg` | Same mark as favicon |
| `web/src/icons/registry.ts` | `ICONS` + `FEATURE_ICONS` map |
| `web/src/components/Icon.tsx` | Inline SVG component |
| `web/src/components/BrandMark.tsx` | Brand `<img>` |

**Feature icon map (ready to wire):**

| Feature | Icon |
|---|---|
| Library / Search | `library` / `search` |
| Architect / Scribe / Editor / Guardian / Curator | `compass` / `pen-line` / `scissors` / `shield` / `palette` |
| Continuity severities | `circle-alert` / `triangle-alert` / `circle-check` |
| Codex types | `users` / `map-pin` / `landmark` / `package` |
| Binder / Corkboard / Outliner | `folder-tree` / `layout-grid` / `layers` |
| Provenance / Consequence | `git-branch` / `waypoints` |
| Comments / Snapshots / Export | `message-square` / `history` / `download` |

---

## File map (upcoming work)

| File | Responsibility |
|---|---|
| `web/src/components/Icon.tsx` | Shared icon primitive |
| `web/src/components/PipelineFlow.tsx` | Agent icons on stages |
| `web/src/components/Inspector.tsx` | Continuity + comments tabs |
| `web/src/routes/ProjectDashboard.tsx` | Continuity health + Codex entry |
| `api/continuity_*.py` / existing engine | Findings API |
| `api/routes.py` | Continuity + Codex endpoints |
| `tests/test_*.py` | API + golden coverage |
| `web/src/**/*.test.tsx` | Panel rendering |

---

## Phase A Finish P1 Surface

### Task A1: Comment anchors in manuscript

- [ ] Confirm Final comments use `from_pos` / `to_pos` end-to-end
- [ ] Render soft highlight decorations in TipTap for active anchors
- [ ] Flag `anchor_status` broken → UI badge with re-quote action
- [ ] Vitest: selection → comment → reload preserves range

### Task A2: P1 close-out

- [ ] MarkdownEditor paths that still use CodeMirror either migrate or stay provenance-only (document which)
- [ ] Update `PLAN.md` P1 → ✅ Complete when green

---

## Phase B Icon chrome pass (quick, unblocks P2 UI)

### Task B1: Wire icons into existing chrome

- [ ] Sidebar Search + Library (started)
- [ ] PipelineFlow stage / agent icons via `FEATURE_ICONS`
- [ ] Inspector tabs: Snapshots `history`, Comments `message-square`
- [ ] Dashboard actions: Export `download`, Plan `compass`
- [ ] Command palette group icons (subtle)

### Task B2: Brand consistency

- [ ] Replace inline Sidebar owl SVG with `BrandMark` (started)
- [ ] Verify favicon in browser tab
- [ ] Optional: apple-touch / OG later in P7 marketing

---

## Phase C P2.1 Continuity surfacing (highest value)

### Task C1: Findings API

- [ ] `GET /api/projects/{id}/continuity` → aggregated findings (severity, chapter, message, check_id)
- [ ] `GET /api/projects/{id}/chapters/{n}/continuity` → chapter slice
- [ ] Re-run after state mutations (existing engine; wrap as service)
- [ ] Pytest: fixture manuscript with known critical + warning

### Task C2: Continuity panel UI

- [ ] Inspector tab **Continuity** with severity icons
- [ ] Click finding → navigate chapter / scroll thread
- [ ] Dashboard **Continuity health** card (counts by severity)
- [ ] Chapter badge from real check results

---

## Phase D P2.2 / P2.3 Codex + portraits

### Task D1: Typed Codex

- [ ] Generalize characters → `character | location | worldbuilding | item`
- [ ] CRUD API + list filters
- [ ] Codex views on Dashboard; type icons from `FEATURE_ICONS`
- [ ] ⌘K entries for Codex jump

### Task D2: Portraits

- [ ] Attach media (P0.3) to Codex entries
- [ ] Show in Cast cards + Inspector
- [ ] Upload affordance with `image` / `upload` icons

---

## Phase E Then (do not start until C+D ship)

| Phase | Name | Why later |
|---|---|---|
| P3 | Consequence preview + provenance ribbon | Needs continuity UI + Final solidity |
| P4 | Binder / corkboard / research | Needs document tree consumers |
| P5–P7 | Word parity, publish, commercial | Product after moat |

---

## Suggested build order (next 2 weeks)

1. **B1** icon chrome (1 day)
2. **A1–A2** finish P1 (2–3 days)
3. **C1–C2** continuity (4–5 days)
4. **D1–D2** Codex + portraits (4–5 days)

---

## Verification

```bash
cd web && npm test && npx tsc -b && npm run build
cd .. && python -m pytest -q
```

Hard-refresh localhost:5173 favicon owl, sidebar icons, proper case labels.

---

## Sources

- [Lucide icons](https://lucide.dev/icons/) ISC, self-hosted via unpkg `lucide-static@0.525.0`
- Product roadmap: `PLAN.md` P1–P2
- Design: `docs/superpowers/specs/2026-08-03-flagship-glass-ui-design.md`
