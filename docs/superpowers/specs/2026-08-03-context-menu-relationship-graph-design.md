# Context Menu + Relationship Graph End-to-End Design

**Date:** 2026-08-03  
**Status:** Approved defaults + R0–R3 shipped; **R4 continuity checks + Guardian neighborhood** implemented 2026-08-04  
**Defaults locked (user: continue):** Codex Chart route · left-click = entity popover · mentions = manual only.
**Fits:** Extends P2 Codex; feeds P3 consequence; prefigures Campfire-style webs without copying module sprawl.

---

## 1. Problem

Authors need two things Scrivener lacks and Campfire over-indexes on:

1. **Instant actions on text and names** select or click → do something (comment, link to Codex, rewrite span, open continuity).
2. **See how people connect** not a flat Cast list, but a living **relationship graph** the Guardian can validate against.

Today Novel OS has Codex cards, TipTap Final, comments, ⌘K (nav-only), and a dormant `Character.relationships: Dict[str, str]`. No context menu. No graph. No typed edges.

---

## 2. Product principles

1. **Left-click discovers; right-click acts.** Left-click on a recognized name opens a lightweight entity popover. Right-click / long-press opens the full action menu. Selection always shows a floating bubble (Word-like).
2. **Graph is a view of Codex edges, not a separate database.** Creating a link in prose, in the menu, or on the chart writes the same edge.
3. **Human confirms AI proposals.** Auto-detected “Lena + Mara = allies?” is a *proposal*, never silent world-state.
4. **Continuity is the consumer.** Edges are ground truth for Guardian + deterministic checks (e.g. “enemies sharing a kiss without arc change”).
5. **Glass UI, proper case, no dashboard clutter.** Chart lives as a project route / Codex mode, not a floating widget zoo.

---

## 3. Context menu system (end-to-end)

### 3.1 Surfaces

| Surface | Trigger | Menu contents |
|---|---|---|
| **Manuscript Final** (TipTap) | Text selection | Comment · Rewrite span (P3) · Link to Codex · Create Codex entry from selection · Copy · Snapshot note |
| **Manuscript Final** | Left-click on marked entity | Popover: Open Codex · Relationships · Appearances · Continuity hits |
| **Manuscript Final** | Right-click (no selection) | Paste · Insert Codex mention · Toggle Notes |
| **Codex card** | Right-click / ⋯ | Edit · Portrait · Link to… · Show on chart · Delete |
| **Chapter board card** | Right-click | Open · Continuity · Plan / Write stage |
| **Relationship chart** | Node / edge click | Edit edge · Open Codex · Hide · Pin |
| **Binder** (later P4) | Right-click | Rename · Status · Split/merge |

### 3.2 Interaction model

```
Selection → BubbleToolbar (left-aligned under selection)
   ├─ Comment
   ├─ Link mention
   ├─ Rewrite… (P3 gate)
   └─ More ▾ → full ContextMenu

Entity mark (auto or manual) → left-click → EntityPopover
   ├─ Portrait + name + role
   ├─ Open in Codex
   ├─ “Connected to” (up to 3 edges)
   └─ Add relationship…

Empty / chrome → right-click → ContextMenu (scoped actions)
```

**Platform:** Right-click on desktop; long-press on trackpad/touch. BubbleToolbar uses left-click selection only (no fight with caret).

### 3.3 Data flow

1. TipTap marks: `codexMention` node or mark `{ entryId, entryType, label }`.
2. Menu action `Link to Codex` → picker (filter characters/locations/items) → insert mark + optional `scene_links` on entry.
3. Menu action `Create from selection` → POST codex with `name=selection`, type guessed or asked → insert mark.
4. All menus share one `ContextMenu` primitive + `useContextActions(scope)` so ⌘K can expose the same commands later.

### 3.4 Scope for v1 vs later

| v1 | Later |
|---|---|
| TipTap selection bubble + right-click | Binder / corkboard menus |
| Entity popover for characters | Locations/items/world |
| Link / create Codex / comment | Rewrite span (needs P3) |
| Codex card ⋯ menu | Drag-to-graph from prose |

---

## 4. Relationship / chart system (end-to-end)

### 4.1 Data model (upgrade)

Replace ad-hoc `relationships: { otherId: "label" }` with typed edges (still JSON in story state):

```json
{
  "id": "rel-012",
  "source_id": "char_001",
  "target_id": "char_003",
  "kind": "character_character",
  "label": "rivals",
  "strength": 0.7,
  "status": "active",
  "since_chapter": 2,
  "notes": "Public allies; private distrust",
  "directed": false,
  "evidence_scene_ids": []
}
```

**Kinds (v1):** `character_character` only.  
**Later:** `character_location`, `character_item`, `faction_faction`.

Store on `StoryState.relationships: Dict[str, RelationshipEdge]` (new). Migrate old `Character.relationships` dict → undirected edges on load.

### 4.2 Views

1. **Relationship chart** `/projects/:id/chart` (or Codex tab “Chart”)
   - Force-directed or tidy radial layout (start force-directed; pin nodes).
   - Nodes = characters (portrait or initial); edges = labeled.
   - Filters: role, active-only, chapter-as-of slider.
2. **Codex detail** “Connections” list under a character (same edges).
3. **Entity popover** mini degree-1 neighborhood.
4. **Continuity** findings cite edge ids when violated.

### 4.3 Creating edges (all write the same store)

| Path | UX |
|---|---|
| Chart | Drag node→node, pick label from presets + Other |
| Codex | “Add connection” on character |
| Context menu | On entity A → “Link to…” → pick B + label |
| AI proposal | Guardian / extractor suggests edge → Accept/Reject queue |

**Preset labels:** ally, rival, family, romantic, mentor, enemy, owes debt, secret, unknown. + Other.

### 4.4 Continuity hooks (moat)

Deterministic checks (cheap):

- Edge says `enemies` but both share POV-friendly intimacy without status change → warning.
- Character appears with someone marked `dead` / removed → critical (ties existing death check).
- Edge `since_chapter` > current chapter but prose treats bond as established → warning.

Guardian prompt: inject neighborhood of characters present in the chapter (1-hop from POV + named cast).

### 4.5 Chart tech (pragmatic)

- **v1:** SVG + simple force layout (d3-force or hand-rolled spring) inside glass panel no heavy graph SaaS.
- **v1.5:** Chapter scrubber dims nodes not yet introduced.
- **Avoid:** Full Campfire module suite, conlang, etc.

---

## 5. End-to-end user journeys

### Journey A Name in prose → world model
1. Author types “Lena Marrow”.
2. (Optional) detector highlights unresolved names.
3. Left-click → Create Codex character / Link existing.
4. Right-click selection → Comment or Link.
5. On chart, Lena appears as a node after create.

### Journey B Map a rivalry
1. Open Chart → drag Lena → Mara → label “rivals”.
2. Edge saved; both Codex cards show connection.
3. Chapter 4 draft softens them; Continuity warns “rivals edge still active”.
4. Author updates edge to “uneasy allies” via popover or accepts AI proposal after consequence preview (P3).

### Journey C Pipeline aware
1. Architect outline mentions both.
2. Scribe drafts scene.
3. Context menu → Rewrite span (P3) → ripple lists relationship edge change as *predicted*.
4. Accept updates Final + edge in one transaction.

---

## 6. Placement in the roadmap

| Slice | Ships | Depends |
|---|---|---|
| **R0** | Shared `ContextMenu` + TipTap selection bubble (Comment, Link stub) | TipTap Final |
| **R1** | `codexMention` marks + entity left-click popover | Codex API |
| **R2** | Typed `RelationshipEdge` + Codex Connections UI | R1 |
| **R3** | Chart route + drag-create edges | R2 |
| **R4** | Continuity checks on edges + Guardian neighborhood inject | R2, P2.1 |
| **R5** | AI relationship proposals + P3 ripple on edges | P3.1 |

Recommended build order after current P2 polish: **R0 → R1 → R2 → R3**, then P3, then R4/R5.

---

## 7. Non-goals (this system)

- Full social-network analytics
- Auto-layout “pretty publish” posters
- Multiplayer co-edit on the graph
- Replacing Codex list view (chart is complementary)

---

## 8. Open decisions (need your call)

1. **Primary chart home:** Dashboard tab under Codex, or dedicated `/chart` route with sidebar link?
2. **Left-click meaning:** Entity popover only (recommended), or also open full context menu?
3. **Mentions in prose:** Manual link only in v1, or also auto-detect known Codex names?

---

## 9. Success criteria

- Author can link a selected name to a character in ≤3 clicks.
- Two characters can be connected on the chart; edge appears on both Codex cards without a second edit.
- Continuity health can cite at least one relationship-based finding.
- No second “shadow” relationship store one edge list, many views.
