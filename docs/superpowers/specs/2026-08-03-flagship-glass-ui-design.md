# Novel OS Flagship Glass UI Revamp

**Date:** 2026-08-03  
**Status:** Draft for approval  
**Approach:** B Flagship hybrid (atmospheric glass on product surfaces; quiet manuscript for writing)  
**Reference:** `glassy-resource-hub-source.zip` (frosted shell, orbs, staggered cards, violet accent)

---

## Intent

Ship an industry-grade visual system for Novel OS: the polish and motion language of the glassy resource hub, adapted for a professional writing product. Library and Dashboard feel cinematic; the Chapter manuscript stays readable for long sessions.

## Locked constraints

| Constraint | Decision |
|---|---|
| Fonts | **SF Pro Display only** for UI + display (self-hosted from `sf-pro-display.zip`). Reader options: SF Pro / Newsreader / Mono. No Geist, Inter, or Google Sans Flex as chrome. |
| Stack currency | Stay on **current** web stack and upgrade where needed: React 19, Vite 8, Tailwind CSS v4, Motion (latest), TipTap 3. Prefer CSS `backdrop-filter` + Motion over legacy animation libs. |
| Accessibility | Visible focus rings; `prefers-reduced-motion`; WCAG AA text on glass and paper; no text over heavy blur without opaque backdrop. |
| Product scope | Visual + motion revamp of existing routes/components. No IA rewrite, no new product features in this pass. |

## Visual system

### Scene (Library, Dashboard, empty/marketing moments)

- Multi-stop gradient: cream → cyan → deep blue (from reference)
- Soft blurred orbs + light sweep behind content
- Subtle animated drift optional; disabled under reduced motion

### Glass chrome

- Frosted surfaces: `backdrop-filter: blur(24px) saturate(135%)`
- Fill: white→cool translucent gradient
- Rim: 1px `rgba(255,255,255,.68)` + inset highlight
- Soft depth shadow (large blur, blue-tinted)
- Radius: shells 28–40px; cards 20–24px; controls full pill where appropriate

### Quiet manuscript (Chapter Final + provenance)

- Opaque warm-white page (`#fdfcfc` / `#ffffff`) **no backdrop blur under prose**
- Surrounding chrome (sidebar, binder, inspector, pipeline) may be glass
- Drop-cap and scene breaks in ink / soft violet, not neon

### Color tokens (target)

| Token | Role |
|---|---|
| Scene gradient | Reference blues/cyans/cream |
| `--color-ink` | `#17213f` (reference ink) |
| `--color-ink-muted` | `#7885a6` |
| `--color-violet` | `#6867ea` (accent active, links, icon tiles) |
| Paper / panel | Near-white opaque for writing; translucent for glass |
| Status | Soft pastel chips (violet/blue/cyan/amber/rose tints) + shape marks |

### Typography

- `--font-sans` / `--font-display` / reader sans → **SF Pro Display**
- Display tracking ≈ `-0.03em` to `-0.035em`
- Eyebrows: 11px, uppercase, wide tracking (reference style)
- Keep existing SF Pro `@font-face` files; verify all weights load

### Motion language (from reference + Motion)

| Moment | Spec |
|---|---|
| Route enter | Fade + 8–12px Y, ~0.35s, snap ease |
| Glass shell | Open: opacity + scale 0.94→1 + translateY; Close: reverse |
| Cards | Stagger 45ms; `cardIn` fade-up 0.5s |
| Hover | translateY(-3px), shadow deepen, violet border whisper |
| Modal / ⌘K | Pop scale 0.8→1 + fade |
| Reduced motion | Instant opacity only; no transform choreography |

## Surfaces in scope

1. **Tokens + scene utilities** in `index.css` (glass, orbs, rim, violet)
2. **App shell** light glass sidebar (not solid black); scene behind Library/Dashboard
3. **Library** glass hub panel, staggered project cards (pastel genre tiles)
4. **Dashboard** same language; action pills; cast cards
5. **Chapter** glass chrome + opaque manuscript; pipeline as soft segmented glass
6. **Overlays** Modal, CommandPalette, Toaster, Confirm as frosted sheets
7. **Motion pass** unify Motion timings with reference easings

## Out of scope

- Replacing SF Pro with Geist/Inter from the zip
- Dark mode (unless requested later as a second glass night theme)
- Binder/corkboard product features (P4)
- Auth / marketing site (P7)

## Success criteria

- [ ] Hard refresh shows SF Pro on chrome and default manuscript
- [ ] Library/Dashboard clearly read as “glass hub” vs current flat eggshell
- [ ] Chapter Final remains readable (opaque page, no blur under text)
- [ ] Motion matches reference feel; reduced-motion respected
- [ ] `npm test` + `tsc` green; no Tailwind `@apply` breakage

## Implementation note

Use **latest compatible** versions already in-repo; bump Motion / TipTap / Vite only if needed for APIs used. Do not introduce a second font family for chrome.
