# Novel OS Monochrome Instrument UI

**Date:** 2026-08-03  
**Status:** Approved (approach B)  
**Related:** `PLAN.md` product phases; this is a chrome/visual pass, not a feature phase.

## Intent

Replace the parchment-and-amber desk with a **light-only, black-and-white precision instrument**: dense Swiss/grid chrome, SF Pro Display type, snappy micro-motion. Manuscript reading stays quiet; chrome is sharp.

## Decisions (locked)

| Axis | Choice |
|------|--------|
| Palette | Monochrome studio black, white, grey ramp only (no hue) |
| Theme | Light only remove dark mode and theme toggle |
| Aesthetic | Precision instrument (micro-radius, hairlines, dense chrome) |
| Status | Combined: tracked labels + shape marks + greyscale chips |
| Type | SF Pro Display as `--font-sans` / `--font-display`; Newsreader remains optional manuscript reader font; Google Sans Code (or SF mono fallback) for mono reader option |

## Color tokens

| Token | Hex | Role |
|-------|-----|------|
| `--color-paper` | `#FFFFFF` | App background |
| `--color-paper-card` | `#F5F5F5` | Panels / cards |
| `--color-paper-line` | `#E8E8E8` | Hairlines |
| `--color-ink` | `#0A0A0A` | Primary fill / sidebar |
| `--color-ink-800` | `#171717` | Hover on ink |
| `--color-ink-700` | `#262626` | Active on ink |
| `--color-ink-line` | `#404040` | Lines on ink |
| `--color-ink-text` | `#0A0A0A` | Body text |
| `--color-ink-muted` | `#525252` | Secondary text |
| `--color-paper-muted` | `#A3A3A3` | Tertiary / placeholders |
| `--color-on-ink` | `#FFFFFF` | Text on black fills |
| `--color-amber` / `--color-amber-deep` | `#0A0A0A` / `#525252` | Aliased to ink/muted (compat for existing class names) |
| Status ramp | black → `#525252` → `#A3A3A3` → outline | planned / drafted / edited / approved |
| `--color-focus` | `#0A0A0A` | Focus ring |
| Danger / diff | black underline or strike + grey fills | no red/green |

Remove body amber wash and warm grain; flat white paper or optional 1% neutral noise only.

## Typography

Self-host SF Pro Display from `sf-pro-display.zip`:

- Upright: Regular, Medium, Bold (primary scale)
- Italics available for emphasis where needed
- Map: UI 12 / 13 / 14; body 16; display 28–40; tracking tight on display (−0.02em)

Reader fonts: SF Pro (sans default), Newsreader (serif), Google Sans Code or `ui-monospace` (mono). Update picker labels.

## Components (crafted primitives)

- `Button` primary (black fill), secondary (hairline), ghost, danger (black outline + bold label)
- `StatusMark` shape ■ ● ▣ ◆ + optional chip + uppercase label
- `Panel` `#F5F5F5` or white + 1px `#E8E8E8`, radius 2–4px
- `Segmented` hairline segmented control
- Keep Modal / Toaster / Confirm; restyle to B&W + snappy motion

## Motion

- Route: 160–200ms opacity + 4px Y (existing Motion)
- Lists: stagger 40ms
- Buttons: scale 0.98 on press
- Modals: 160ms scale/fade
- Respect `prefers-reduced-motion` / `MotionConfig reducedMotion="user"`

## Surfaces in scope

1. Tokens + SF Pro faces + theme bootstrap (light lock)
2. Sidebar (B&W mark, no ThemeToggle)
3. Library (`ProjectsList`, `ProjectCard`)
4. Dashboard (`ProjectDashboard`, `ChapterBoard`, `Outliner`)
5. Chapter (`ChapterView`, `PipelineFlow`, `FinalEditor` chrome, `Inspector`)
6. Overlays (`Modal`, `CommandPalette`, `Toaster`, `Confirm`, `ShortcutsHelp`)
7. Status / Diff / Breadcrumbs / ErrorBoundary

## Out of scope

- Binder tree / corkboard product features (P4)
- Auth / marketing site (P7)
- Changing agent pipelines or API contracts

## Success

- No amber, blue, green, purple, or warm parchment in UI chrome
- SF Pro Display loads for chrome and default prose
- Theme toggle gone; always light
- Status readable without hue
- Existing Vitest suite green; visual spot-check Library → Chapter
