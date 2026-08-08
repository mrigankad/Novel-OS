# Product UX Foundation Design

**Date:** 2026-08-03  
**Status:** Approved to build (user: “okay start building”)  
**Audience:** Both plotters and mature-fiction writers (option C), with continuity as the long-term wedge.

## Goals (this slice)

1. **Richer Library cards** taller manuscript tiles (title, genre, words, chapters, status, rating badge).
2. **Studio Settings** see live LLM provider/model; switch preset (Quality / Fast / Local / Mature-capable); BYOK fields for OpenRouter / local.
3. **Content rating** per-project `general` | `mature` (not “NSFW product branding”).
4. **First-run** welcome + LLM health gate before agents feel broken; dismissible tour shell.

## Non-goals (later)

- Hosted NSFW models or Muse-like proprietary uncensored model
- Per-agent model overrides
- Full 6-step interactive sample novel (shell + CTA only this slice)
- Continuity panel UI (next phase)

## Backend

- Extend `ProjectSummary`: `author`, `word_count`, `drafted_count`, `content_rating`, `updated_at`
- `GET/PUT /api/studio/llm` status + write `studio_settings.json`, apply to `os.environ`
- `PATCH /api/projects/{id}` `content_rating` (and optional title/genre later)

## UI

- Redesigned `ProjectCard` (vertical, not thin chip)
- `/settings` route + Sidebar link
- Library welcome banner when onboarding incomplete or LLM missing

## Constraints

- Proper case chrome; glass + SF Pro; opaque manuscript unchanged
- Never claim Claude is uncensored; Mature → recommend Local / OpenRouter
