# What Writing a Novel Actually Involves — and Where Novel OS Should Stand

**Written:** 2026-08-08
**Method:** the full job list from an author's seat, checked against published research
on where writers stall and what they say about the tools they already pay for
(sources at the end), then turned into an interaction design.
**Companion to:** [`PLAN.md`](../../../PLAN.md) (phases) and
[`2026-08-08-full-stack-architecture-and-buildout.md`](../plans/2026-08-08-full-stack-architecture-and-buildout.md) (storage).

---

## Part 1 — The whole job, as an author sees it

Not "features." The actual work, in the order it bites.

### A. Before there is a manuscript

1. Premise and the "what if" — the one sentence that survives the whole book
2. Genre and market position; comparable titles; expected length and conventions
3. Cast: names, wants, wounds, contradictions, arcs, who changes and how
4. Relationship web: who owes whom, who lies to whom, and when that changes
5. World: geography, rules, institutions, technology or magic, economy, language
6. Timeline: story-time vs page-time, ages, seasons, travel durations
7. Structure: act breaks, midpoint reversal, set pieces, the ending you're aiming at
8. POV and tense decisions; whose head, how many heads, how close
9. Voice: the sentence-level identity that makes the book *yours*
10. Research: the real-world facts the story leans on, and where they live

### B. Drafting

11. The blank page each morning — what happens in *this* scene
12. Scene-level goal / conflict / turn
13. Actually producing words; hitting a daily target; not stopping to edit
14. Remembering what you already decided 200 pages ago
15. Keeping the voice steady across months of writing on different days
16. Continuity as you go: eye colour, who knows what, what time it is
17. Threads: planting, escalating, paying off, and not dropping any
18. **The middle** — see Part 2, this is the one that kills books
19. Recording the things you'll fix later without stopping to fix them now
20. Momentum and morale across a 6–18 month solo project

### C. Revision

21. Reading the whole thing and seeing what it *actually* is vs what you meant
22. Structural: cut, reorder, merge, split, add the missing scene
23. Arc: does the protagonist change, is the change earned
24. Pacing: where does it drag, where is it rushed
25. Continuity audit: the details you got wrong across 90,000 words
26. Line editing: rhythm, echoes, filter words, verb strength
27. Dialogue: distinct voices, subtext, no exposition dumps
28. Copyedit and proof: grammar, spelling, invented-name consistency
29. Beta feedback: collecting it, weighing it, deciding what to ignore
30. Version control: keeping the cut scene you might want back

### D. Finishing and out the door

31. Front and back matter, chapter titles, dedication, acknowledgements
32. Compile to DOCX / EPUB / PDF with correct formatting
33. Query letter, synopsis, blurb, comps — a different skill entirely
34. Submission or self-pub production tracking
35. Marketing copy, series bible for book two

**35 jobs. Novel OS currently touches about 22 of them.** The gaps are
concentrated in D (publishing, 31–35) and in the craft half of C (26–29).

---

## Part 2 — Where it's genuinely hard

Four load-bearing findings. Each one is a design constraint, not trivia.

### 2.1 The middle is where books die

Writers have "a clear and compelling sense of where their story begins and ends,
but often less of an idea about how, exactly, they will get there." The failure is
diagnosable, not mystical: **middles sag because the protagonist becomes
reactive** — things happen *to* them and they stop pursuing anything — and because
act two must do two jobs at once, raising pressure while deepening character.

> **Design consequence.** "Sagging middle" sounds subjective but decomposes into
> signals a world model can actually measure: chapters where the POV character
> takes no action with a stated goal, threads that were planted and haven't
> escalated in N chapters, stretches with no reversal, scenes where nothing about
> the character's want changes. Novel OS has the state to compute all four.
> **Nobody ships this.** See §4.3.

### 2.2 Writers cannot see their own continuity errors

The reason is specific and unfixable by effort: writers are so close to the book
that **the logic is in their head, not on the page**. The standard professional
remedies are to put the manuscript in a drawer for two to eight weeks, keep a
spiral notebook, and run manual searches — literally grepping the draft for
"redhead" or "car". Common failures are physical description drift, timeline
contradictions, and object tracking (things lost that reappear).

> **Design consequence.** This is the strongest existing moat and it is
> *deterministic* — no model required. It also explains the emotional register
> the feature needs: findings are a relief, not an accusation.

### 2.3 AI cannot tell an intentional inconsistency from an error

Current tools cannot distinguish an unreliable narrator, deliberate
foreshadowing, or a character who lies from an actual mistake. They also can't
judge thematic consistency or pacing rhythm.

> **Design consequence, and this one is missing from Novel OS today.** Every
> finding needs **"this is intentional" — and it must stick.** A continuity panel
> that re-raises a dismissed finding every run trains the writer to ignore the
> panel, which destroys the moat. Dismissals belong in `story_state.json` next to
> the fact they exempt, with the writer's reason, so the Guardian sees them too.

### 2.4 Writers use AI where it is furthest from their voice

BookBub's May 2025 survey of 1,200+ authors: **~45% use AI**, concentrated in
**research (81%), marketing copy (73%), outlining (72%), editing (70%)**.

Prose generation is not near the top. And the sharpest criticism of the best
prose model on the market is that its output "sound[s] like writing without quite
feeling like **your** writing" — passages that "sound fine until you notice they
belong to a slightly different version of the book."

> **Design consequence, and it is uncomfortable.** Novel OS's pipeline centres a
> Scribe that drafts chapters — the one job the market wants least and judges
> hardest. The engine is right; **the emphasis is wrong.** Reposition drafting as
> one available mode, not the spine, and lead with the four jobs writers actually
> want help with. See §4.1.

### 2.5 The three competitors each fail at the same seam: getting started

| Tool | The complaint, in writers' words |
|---|---|
| Sudowrite | "The tool never really disappears." AI is "the driver and you're along for the ride." Story Bible needs **manual re-entry of information already in the draft**. Credit meter creates "credit anxiety" that changes behaviour |
| NovelCrafter | "Why am I doing this configuration work at all?" BYO-key setup before anything works — "easily the roughest start" |
| Scrivener | Steep learning curve; writers "spent too much time on tutorials they didn't need"; project notes "cluttered and overwhelming in large projects" |

> **Design consequence.** All three lose people in the first hour. That is the
> cheapest market share in this category, and it is a *design* win, not a
> features win.

---

## Part 3 — Where AI belongs, and where it must stay out

The honest split. Novel OS's advantage is that it can be deterministic where
determinism is possible, so AI is reserved for what only AI can do.

### Deterministic — no model, instant, free, always right

Continuity checks · thread tracking · timeline arithmetic · word frequency and
echo detection · reading time · targets and streaks · search · relationship
integrity · **stall detection (§4.3)**

These should run constantly and silently. They cost nothing, so there is no
reason to batch them behind a button.

### AI, proposing — always reviewable, never applied silently

| Job | Why AI earns its place |
|---|---|
| Research answers, in-context | 81% of authors already do this in another tab |
| Outlining and "what could happen next" | 72% usage; and it's **reaction material**, which is what unblocks people |
| Codex extraction from existing prose | Kills the single worst onboarding friction in the category |
| Synopsis and blurb | Compression is genuinely hard for the person who wrote it |
| Line-edit suggestions | 70% usage; lands as tracked changes, never as an overwrite |
| Consequence preview | Only possible because a world model exists |
| Marketing copy, query, comps | Different skill, low voice risk, real drudgery |

### AI, off by default

Whole-chapter prose generation. Keep it — some writers want it and it costs you
nothing to offer. But it must not be the default path, because it is the mode
most likely to produce a book that isn't the writer's.

### Never AI

Judging whether the writing is *good*. Deciding what the book is about. Silent
edits. Anything that resolves a suggestion without a human clicking accept.

---

## Part 4 — The design decisions

### 4.1 Replace the stage pipeline with the three modes writers live in

Today the UI exposes `Outline → Draft → Revised → Final`. That is the **engine's**
model leaking into the interface. No novelist thinks "I am in the revised stage."

They think **Plan / Write / Revise** — and they move between them constantly, not
in sequence.

```
┌─────────────────────────────────────────────────────┐
│  ◐ Plan        ● Write        ○ Revise      ⌘1 2 3  │
└─────────────────────────────────────────────────────┘
```

| Mode | The screen is optimised for | Rails |
|---|---|---|
| **Plan** | Structure and world. Corkboard, outliner, codex, relationship chart, timeline | Binder + Codex |
| **Write** | Producing words today. Manuscript, nothing else. Targets and continuity are ambient | Both collapsed by default |
| **Revise** | Seeing the book as it is. Diff, continuity, comments, tracked changes, statistics | Binder + Inspector |

The four stages stay — as **provenance**, in the Inspector, where a writer can ask
"where did this paragraph come from." That is the honest home for them: they're a
history, not a workflow.

### 4.2 Onboarding: import first, extract automatically

The category's shared weak point (§2.5). The first run must not be a form.

```
Drop a .docx / .md / paste                     ← nothing to configure
        ↓
Chapters detected · 47 found                   ← binder built for them
        ↓
"We found 23 characters, 8 places, 14 threads" ← Codex EXTRACTED, not typed
   [Review 23 proposals]  [Skip for now]       ← proposals, never silent writes
        ↓
"3 continuity issues in your draft"            ← the moat, in the first 60 seconds
```

This is the P2 tail item ("Codex auto-extract proposals") and it has been
mis-scoped as a nice-to-have. **It is the single highest-leverage unbuilt
feature in the product**, because it converts the competitor's worst hour into
Novel OS's best minute.

### 4.3 The Stall Detector — the feature nobody else can build

§2.1 says the middle kills books. Novel OS holds cast wants, thread states,
per-chapter POV and status, and relationship edges. So compute:

| Signal | Deterministic rule |
|---|---|
| **Reactive protagonist** | ≥3 consecutive chapters where the POV character has no scene goal recorded |
| **Stalled thread** | Planted, not escalated or paid off within N chapters |
| **Flat stretch** | No reversal, no relationship-edge change, no thread state change across a run of chapters |
| **Absent want** | Character's stated want unchanged since introduction past the midpoint |

Surface it as a **shape of the book** strip on the dashboard — one row per
chapter, height by tension, colour by thread activity — with the sagging run
highlighted. The AI's only job is the *sentence* explaining a flagged run, clearly
labelled as interpretation.

This is the third moat, alongside deterministic continuity and consequence
preview, and it is the one a writer would switch tools for.

### 4.4 Continuity findings need memory

From §2.3. Every finding gets three actions, not two:

```
⚠ Mara's eyes: grey in ch.3, green in ch.11
   [Go to ch.11]  [Fix]  [Intentional — she's lying about it ▾]
```

`Intentional` writes an exemption into `story_state.json` with the reason, scoped
to that fact. The Guardian reads exemptions, so the AI stops re-raising it too.
Without this, the panel becomes noise within a week.

### 4.5 The tool must disappear while writing

Directly against Sudowrite's "the tool never really disappears."

- **Write mode opens with both rails collapsed.** The manuscript is the page.
- **No AI affordance appears unless the writer asks.** No hovering buttons, no
  ghost text, no suggestions volunteered mid-sentence.
- **Continuity runs silently**; a single dot in the status bar turns amber. It
  never opens a panel, never steals focus.
- **No meter, ever.** Zero marginal cost via the CLI is not just a price
  advantage — "credit anxiety" is a *design* defect Novel OS structurally does
  not have. Never introduce a token counter into the writing surface.
- **One ambient number**: words today. Everything else is on request.

### 4.6 One AI entry point, one shape

Instead of scattered AI buttons: **select text → one bar**, and every AI action in
the product returns the same three-part answer.

```
   ┌──────────────────────────────────────────────┐
   │  ✎ Rewrite   ⌦ Expand   ↯ Consequence   ⌕ Ask │
   └──────────────────────────────────────────────┘

   Result, always in this shape:
   ─────────────────────────────────────────
   The proposal            → as tracked changes
   What it breaks          → deterministic, certain
   What it might mean      → labelled PREDICTED
   [Reject]              [Accept]
```

One learned interaction covers rewrite, expand, consequence, and continue. This
is how you get Scrivener's power without Scrivener's tutorials.

### 4.7 Capture without stopping

Job 19 — recording what you'll fix later without breaking flow. A single key
(`⌘.`) drops a margin note at the cursor and returns focus to the manuscript
immediately. Notes collect in Revise mode as a punch list. This is what the
spiral notebook in §2.2 actually is, and it belongs in the product.

---

## Part 5 — What this changes, in priority order

1. **Codex auto-extract on import** (§4.2) — promote from P2 tail to next-up. Kills the category's worst friction.
2. **Intentional-dismissal with memory** (§4.4) — small, and the continuity moat degrades to noise without it.
3. **Plan / Write / Revise modes** (§4.1) — re-frames the existing surfaces; mostly routing and default rail state.
4. **Stall detector + shape strip** (§4.3) — new deterministic checks on state that already exists. The third moat.
5. **Unified selection bar** (§4.6) — consolidates AI entry points already built.
6. **Quick capture** (§4.7) — one keybinding, one list.
7. Then P5.2 styles → P6 compile, which is where jobs 31–35 finally get answered.

**What to stop leading with:** whole-chapter generation. Keep the Scribe, demote
the emphasis. The market is telling us plainly that drafting is the job it wants
least and judges hardest, and it is the one place Novel OS competes on someone
else's ground instead of its own.

---

## Sources

- [Wading Through The Middle: The Hardest Part of Drafting A Novel — S. M. Mitchell](https://smmitchell.com/2023/12/30/wading-through-the-middle-the-hardest-part-of-drafting-a-novel/)
- [The Saggy Middle: How to Fix a Novel That Stalls in Act Two](https://www.ebookpbook.com/2026/07/16/fix-saggy-middle-novel/)
- [How to Fix the Sagging Middle of Your Novel — Novela Studio](https://novela.so/en/blog/sagging-middle-novel-guide)
- [How to check for consistency when revising your novel manuscript — Write on the World](https://writeontheworld.wordpress.com/2024/11/18/how-to-check-for-consistency-when-revising-your-novel-manuscript/)
- [5 Ways to Avoid Continuity Gaffes — Career Authors](https://careerauthors.com/5-ways-to-avoid-continuity-gaffes/)
- [Best AI for Novel Continuity Checking (2026) — Inkfluence AI](https://www.inkfluenceai.com/blog/best-ai-novel-continuity-checking-2026)
- [Sudowrite Review: Tested on a 40,000-Word Manuscript — Ilam Padmanabhan](https://ilampadmanabhan.medium.com/sudowrite-review-i-tested-it-on-a-40-000-word-manuscript-heres-my-honest-verdict-april-2026-951b674dccea)
- [Novelcrafter Review: Powerful for Fiction Writers, Frustrating to Set Up — Ilam Padmanabhan](https://ilampadmanabhan.medium.com/novelcrafter-review-64d391c629a2)
- [Sudowrite vs Novelcrafter — Ilam Padmanabhan](https://ilampadmanabhan.medium.com/sudowrite-vs-novelcrafter-bdc3f33ba95f)
- [How Authors Are Really Using AI (BookBub survey, 1,200+ authors) — Authors A.I.](https://authors.ai/how-authors-are-really-using-ai/)
- [Scrivener Review: A Great 20% Discount (But Why I Don't Use It) — Kindlepreneur](https://kindlepreneur.com/scrivener-review/)
- [Scrivener Reviews 2026 — Capterra](https://www.capterra.com/p/180597/Scrivener/reviews/)
