/**
 * Track changes (PLAN.md P5.1) - the document half.
 *
 * Suggestions live as two marks on text nodes:
 *
 *   suggestionInsert   proposed new text; not part of the manuscript yet
 *   suggestionDelete   existing text proposed for removal; still the manuscript
 *
 * Accepting and rejecting are pure transformations of the ProseMirror JSON
 * rather than position arithmetic on a live editor. Positions shift under every
 * concurrent edit, and getting them wrong silently mangles prose; a JSON
 * transform is exactly testable and cannot address the wrong span. `api/richtext.py`
 * applies the same rule server-side, so the markdown agents read is always the
 * reject-all view.
 */

import type { PMDoc } from "./richText";

export const SUGGESTION_INSERT = "suggestionInsert";
export const SUGGESTION_DELETE = "suggestionDelete";

export type SuggestionKind = typeof SUGGESTION_INSERT | typeof SUGGESTION_DELETE;

export type Suggestion = {
  id: string;
  kind: SuggestionKind;
  author: string;
  /** ISO timestamp, or "" when the mark predates the attribute. */
  at: string;
  /** The proposed text (insert) or the text proposed for removal (delete). */
  text: string;
};

type JSONNode = {
  type?: string;
  text?: string;
  marks?: { type?: string; attrs?: Record<string, unknown> }[];
  content?: JSONNode[];
};

function suggestionMark(node: JSONNode) {
  return (node.marks || []).find(
    (m) => m.type === SUGGESTION_INSERT || m.type === SUGGESTION_DELETE,
  );
}

/**
 * Every pending suggestion, in document order, adjacent runs of the same id
 * merged so one typed word is one entry rather than one per text node.
 */
export function listSuggestions(doc: PMDoc | null | undefined): Suggestion[] {
  const out: Suggestion[] = [];

  const walk = (node: JSONNode) => {
    if (node.type === "text") {
      const mark = suggestionMark(node);
      if (mark) {
        const attrs = mark.attrs || {};
        const id = String(attrs.id ?? "");
        const prev = out[out.length - 1];
        if (prev && prev.id === id && id !== "") {
          prev.text += node.text || "";
        } else {
          out.push({
            id,
            kind: mark.type as SuggestionKind,
            author: String(attrs.author ?? ""),
            at: String(attrs.at ?? ""),
            text: node.text || "",
          });
        }
      }
      return;
    }
    for (const child of node.content || []) walk(child);
  };

  walk((doc || {}) as JSONNode);
  return out;
}

export function hasSuggestions(doc: PMDoc | null | undefined): boolean {
  return listSuggestions(doc).length > 0;
}

/** Which suggestions a resolution keeps as text, and which it drops. */
type Resolution = "accept" | "reject";

function keepsText(kind: SuggestionKind, how: Resolution): boolean {
  // Accepting an insertion keeps the new words; accepting a deletion removes
  // the old ones. Rejecting is the mirror.
  if (kind === SUGGESTION_INSERT) return how === "accept";
  return how === "reject";
}

function resolve(doc: PMDoc, how: Resolution, ids: Set<string> | null): PMDoc {
  const applies = (id: string) => ids === null || ids.has(id);

  const walk = (node: JSONNode): JSONNode | null => {
    if (node.type === "text") {
      const mark = suggestionMark(node);
      if (!mark) return node;
      const id = String((mark.attrs || {}).id ?? "");
      if (!applies(id)) return node;

      if (!keepsText(mark.type as SuggestionKind, how)) return null;
      // Kept: the words become ordinary prose, so the suggestion mark goes but
      // any formatting marks the author applied stay.
      const marks = (node.marks || []).filter(
        (m) => m.type !== SUGGESTION_INSERT && m.type !== SUGGESTION_DELETE,
      );
      const next: JSONNode = { ...node };
      if (marks.length) next.marks = marks;
      else delete next.marks;
      return next;
    }

    if (node.content) {
      const content = node.content
        .map(walk)
        .filter((c): c is JSONNode => c !== null);
      // A paragraph emptied by this resolution stays as an empty paragraph:
      // dropping the block would merge it with its neighbour and silently
      // restructure the chapter.
      return { ...node, content };
    }
    return node;
  };

  return walk(doc as JSONNode) as PMDoc;
}

export function acceptSuggestion(doc: PMDoc, id: string): PMDoc {
  return resolve(doc, "accept", new Set([id]));
}

export function rejectSuggestion(doc: PMDoc, id: string): PMDoc {
  return resolve(doc, "reject", new Set([id]));
}

export function acceptAllSuggestions(doc: PMDoc): PMDoc {
  return resolve(doc, "accept", null);
}

export function rejectAllSuggestions(doc: PMDoc): PMDoc {
  return resolve(doc, "reject", null);
}

/**
 * The manuscript as it stands if every pending change were rejected - the same
 * view `api/richtext.py` writes to disk for the agents.
 */
export function acceptedDoc(doc: PMDoc): PMDoc {
  return rejectAllSuggestions(doc);
}

let counter = 0;

/** Ids only need to be unique within a document. */
export function newSuggestionId(): string {
  counter += 1;
  return `s${Date.now().toString(36)}${counter.toString(36)}`;
}
