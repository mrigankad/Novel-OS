/**
 * The one list of things you can do to a selection (design spec §4.6).
 *
 * Novel OS had accumulated three ways in - a right-click menu, a floating
 * bubble that was written but never wired, and a chat box - each offering a
 * slightly different set. That is how a product ends up needing tutorials.
 *
 * Defining the actions once means the bar and the context menu cannot drift
 * apart, and a writer who learns one has learned both.
 */

import type { IconName } from "../components/Icon";

export type SelectionActionId =
  | "rewrite"
  | "expand"
  | "comment"
  | "link"
  | "create"
  | "ask";

export type SelectionAction = {
  id: SelectionActionId;
  label: string;
  icon: IconName;
  /** Shown in the bar; the rest live behind the right-click menu. */
  primary?: boolean;
  /** Actions that operate on the selected words need one to exist. */
  needsSelection: boolean;
};

/**
 * Pure data, with no handlers attached: each surface maps an id to behaviour
 * itself. That keeps the vocabulary in one place while leaving the editor's
 * live selection where it belongs, inside the component that owns the editor.
 *
 * Order is deliberate: the two that change prose come first, because they are
 * why a writer selected anything, and both return the same three-part answer -
 * the proposal as tracked changes, what it breaks, what it might mean.
 */
export const SELECTION_ACTIONS: readonly SelectionAction[] = [
  { id: "rewrite", label: "Rewrite", icon: "sparkles", primary: true, needsSelection: true },
  { id: "expand", label: "Expand", icon: "pen-line", primary: true, needsSelection: true },
  { id: "comment", label: "Comment", icon: "message-square", primary: true, needsSelection: true },
  { id: "link", label: "Link to Codex", icon: "users", needsSelection: true },
  { id: "create", label: "New Codex entry", icon: "plus", needsSelection: true },
  { id: "ask", label: "Ask Scribe…", icon: "bot", needsSelection: false },
];

/** The subset shown in the floating bar - the rest stay one right-click away. */
export const BAR_ACTIONS: readonly SelectionAction[] =
  SELECTION_ACTIONS.filter((a) => a.primary);
