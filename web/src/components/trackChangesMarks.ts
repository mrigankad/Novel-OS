/**
 * Track changes (PLAN.md P5.1) - the editor half.
 *
 * Two marks plus a "suggest mode" that rewrites ordinary editing into
 * proposals: typing becomes marked insertions, and deleting marks the words
 * instead of removing them. Nothing here resolves a suggestion - accept and
 * reject are pure JSON transforms in `lib/trackChanges.ts`, because position
 * arithmetic against a live document is the part that silently mangles prose.
 *
 * The rule this enforces is P3.3's: AI proposes, the human disposes. An agent
 * revision arrives as suggestions, never as an overwrite of Final.
 */

import { Extension, Mark, mergeAttributes } from "@tiptap/core";
import { Plugin, PluginKey, Selection } from "@tiptap/pm/state";
import { ReplaceStep } from "@tiptap/pm/transform";
import {
  SUGGESTION_DELETE,
  SUGGESTION_INSERT,
  newSuggestionId,
} from "../lib/trackChanges";

/** Marks this extension's own transactions so it never re-processes them. */
const trackKey = new PluginKey("novelOsTrackChanges");

const suggestionAttributes = {
  id: { default: null as string | null },
  author: { default: "" },
  at: { default: "" },
};

function attrsToDataset(attrs: Record<string, unknown>) {
  return {
    "data-suggestion-id": attrs.id,
    "data-suggestion-author": attrs.author,
    "data-suggestion-at": attrs.at,
  };
}

export const SuggestionInsert = Mark.create({
  name: SUGGESTION_INSERT,
  inclusive: true,
  excludes: SUGGESTION_DELETE,
  addAttributes: () => suggestionAttributes,
  parseHTML: () => [{ tag: "ins[data-suggestion-id]" }],
  renderHTML({ HTMLAttributes }) {
    return [
      "ins",
      mergeAttributes(attrsToDataset(HTMLAttributes), { class: "pm-suggest-insert" }),
      0,
    ];
  },
});

export const SuggestionDelete = Mark.create({
  name: SUGGESTION_DELETE,
  inclusive: false,
  excludes: SUGGESTION_INSERT,
  addAttributes: () => suggestionAttributes,
  parseHTML: () => [{ tag: "del[data-suggestion-id]" }],
  renderHTML({ HTMLAttributes }) {
    return [
      "del",
      mergeAttributes(attrsToDataset(HTMLAttributes), { class: "pm-suggest-delete" }),
      0,
    ];
  },
});

export interface TrackChangesOptions {
  /** Name recorded on every suggestion this session produces. */
  author: string;
}

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    trackChanges: {
      setSuggesting: (on: boolean) => ReturnType;
    };
  }
}

export const TrackChanges = Extension.create<
  TrackChangesOptions,
  { suggesting: boolean }
>({
  name: "trackChanges",

  addOptions() {
    return { author: "" };
  },

  addStorage() {
    return { suggesting: false };
  },

  addCommands() {
    return {
      setSuggesting:
        (on: boolean) =>
        () => {
          this.storage.suggesting = on;
          return true;
        },
    };
  },

  addKeyboardShortcuts() {
    const swallowDeletion = (direction: -1 | 1) => () => {
      if (!this.storage.suggesting) return false;
      const { state, view } = this.editor;
      const { from, to, empty } = state.selection;

      const start = empty ? (direction === -1 ? from - 1 : from) : from;
      const end = empty ? (direction === -1 ? from : from + 1) : to;
      if (start < 0 || end > state.doc.content.size || start >= end) return false;

      const insertType = state.schema.marks[SUGGESTION_INSERT];
      const deleteType = state.schema.marks[SUGGESTION_DELETE];

      // Backspacing over your own un-accepted insertion should take the words
      // away, not propose deleting text that was never in the manuscript.
      let allOwnInsertion = true;
      state.doc.nodesBetween(start, end, (node) => {
        if (node.isText && !insertType.isInSet(node.marks)) allOwnInsertion = false;
      });
      if (allOwnInsertion) return false;

      const tr = state.tr
        .addMark(
          start,
          end,
          deleteType.create({
            id: newSuggestionId(),
            author: this.options.author,
            at: new Date().toISOString(),
          }),
        )
        .setMeta(trackKey, true);
      // Step over the struck text rather than sitting inside it, so holding
      // Backspace keeps marking earlier words instead of stalling.
      tr.setSelection(Selection.near(tr.doc.resolve(start), direction));
      view.dispatch(tr);
      return true;
    };

    return {
      Backspace: swallowDeletion(-1),
      Delete: swallowDeletion(1),
    };
  },

  addProseMirrorPlugins() {
    const options = this.options;
    const storage = this.storage;

    return [
      new Plugin({
        key: trackKey,
        appendTransaction(transactions, _oldState, newState) {
          if (!storage.suggesting) return null;
          if (!transactions.some((t) => t.docChanged)) return null;
          // Our own mark-application must not be marked again.
          if (transactions.some((t) => t.getMeta(trackKey))) return null;

          const insertType = newState.schema.marks[SUGGESTION_INSERT];
          if (!insertType) return null;

          const tr = newState.tr;
          const id = newSuggestionId();
          const mark = insertType.create({
            id,
            author: options.author,
            at: new Date().toISOString(),
          });

          let touched = false;
          for (const transaction of transactions) {
            transaction.steps.forEach((step, index) => {
              if (!(step instanceof ReplaceStep) || step.slice.size === 0) return;
              const mapping = transaction.mapping.slice(index);
              const from = mapping.map(step.from, -1);
              const to = mapping.map(step.from + step.slice.size, 1);
              if (to <= from) return;
              tr.addMark(from, to, mark);
              touched = true;
            });
          }

          if (!touched) return null;
          return tr.setMeta(trackKey, true);
        },
      }),
    ];
  },
});
