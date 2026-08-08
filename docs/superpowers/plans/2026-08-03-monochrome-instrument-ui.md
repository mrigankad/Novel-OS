# Monochrome Instrument UI Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a light-only black-and-white precision-instrument UI with SF Pro Display across Novel OS web.

**Architecture:** Retoken `index.css`, self-host SF Pro, lock theme to light, rebuild/restyle shared chrome and route surfaces without changing API contracts.

**Tech Stack:** React 19, Tailwind v4, Motion, TipTap, Vitest

**Spec:** `docs/superpowers/specs/2026-08-03-monochrome-instrument-ui-design.md`

## Global Constraints

- Palette: black / white / grey only no hue accents
- Light theme only remove dark mode + ThemeToggle
- Font: SF Pro Display for sans/display; Newsreader optional for reader serif
- Radius: 2–4px chrome; keep accessibility focus rings
- Respect `prefers-reduced-motion`

---

### Task 1: Fonts + tokens + theme lock

**Files:** `web/src/fonts/*`, `web/src/fonts/sf-pro.css`, `web/src/main.tsx`, `web/src/index.css`, `web/src/theme.ts`, `web/index.html`, remove ThemeToggle usage

- [ ] Copy SF Pro OTF files into `web/src/fonts/sf-pro/`
- [ ] Add `@font-face` CSS for Regular / Medium / Bold (+ italics as needed)
- [ ] Point `--font-sans` / `--font-display` / reader-sans at SF Pro Display
- [ ] Rewrite `@theme` to monochrome ramp; alias amber → ink/muted; greyscale status
- [ ] Remove dark `[data-theme="dark"]` overrides; force light in `theme.ts`
- [ ] Flat white body background (no amber gradient)
- [ ] Update `theme-color` meta to `#FFFFFF`
- [ ] Update reader font labels; adjust readerFont tests if needed

### Task 2: Primitives + StatusMark

**Files:** `web/src/components/ui/Button.tsx`, `StatusMark.tsx`, `StatusPill.tsx`, `index.css` status classes

- [ ] Add Button variants (primary / secondary / ghost)
- [ ] Rebuild StatusPill with shape + chip + label (combined status language)
- [ ] Restyle `.status-pill` CSS to greyscale

### Task 3: Shell + overlays

**Files:** `Sidebar.tsx`, `App.tsx`, `Modal.tsx`, `CommandPalette.tsx`, `Toaster.tsx`, `Confirm.tsx`, `ShortcutsHelp.tsx`, delete or gut `ThemeToggle.tsx`

- [ ] B&W sidebar mark and denser rail; remove ThemeToggle
- [ ] Restyle overlays to hairline + black/white motion

### Task 4: Library + Dashboard

**Files:** `ProjectsList.tsx`, `ProjectCard.tsx`, `ProjectDashboard.tsx`, `ChapterBoard.tsx`, `Outliner.tsx`, `Breadcrumbs.tsx`

- [ ] Strip amber; grey spines; instrument cards; snappy stagger

### Task 5: Chapter workspace

**Files:** `ChapterView.tsx`, `PipelineFlow.tsx`, `FinalEditor.tsx`, `Inspector.tsx`, `DiffView.tsx`, `ErrorBoundary.tsx`, prose CSS

- [ ] Pipeline as greyscale meter; inspector/diff B&W; drop-cap/hr ink not amber

### Task 6: Verify

- [ ] `npm test` green
- [ ] `npx tsc -b` clean
- [ ] Spot-check in browser
