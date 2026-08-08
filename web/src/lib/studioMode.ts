/**
 * The three modes a novelist actually works in (design spec §4.1).
 *
 * The UI used to expose the engine's stage pipeline - Outline → Draft →
 * Revised → Final - as if it were a workflow. It isn't: no novelist thinks "I
 * am in the revised stage." They think Plan, Write, or Revise, and they move
 * between those constantly rather than in sequence. The four stages remain, in
 * the Inspector, as *provenance* - a history of where a paragraph came from,
 * which is their honest home.
 *
 * Mode is a view preference, not project data: it belongs in localStorage, not
 * story_state.json, because it describes what the writer is doing this hour.
 */

export type StudioMode = "plan" | "write" | "revise";

export const STUDIO_MODES: { id: StudioMode; label: string; hint: string }[] = [
  { id: "plan", label: "Plan", hint: "Structure and world" },
  { id: "write", label: "Write", hint: "Words today, nothing else" },
  { id: "revise", label: "Revise", hint: "The book as it is" },
];

const KEY = "novelos-studio-mode";

export function getStudioMode(): StudioMode {
  const saved = localStorage.getItem(KEY);
  return saved === "plan" || saved === "write" || saved === "revise" ? saved : "write";
}

export function setStudioMode(mode: StudioMode): void {
  localStorage.setItem(KEY, mode);
  window.dispatchEvent(new CustomEvent(MODE_EVENT, { detail: mode }));
}

/** Broadcast so every mounted surface reacts without prop-drilling through routes. */
export const MODE_EVENT = "novelos:studio-mode";

/**
 * What each mode does to the chapter surface.
 *
 * Write collapses both rails on purpose: the strongest complaint about the
 * best-funded tool in this category is that it "never really disappears".
 */
export function chapterLayoutFor(mode: StudioMode): {
  binder: boolean;
  inspector: boolean;
  inspectorTab: "versions" | "comments" | "continuity";
} {
  switch (mode) {
    case "plan":
      return { binder: true, inspector: false, inspectorTab: "versions" };
    case "revise":
      return { binder: true, inspector: true, inspectorTab: "continuity" };
    default:
      return { binder: false, inspector: false, inspectorTab: "versions" };
  }
}
