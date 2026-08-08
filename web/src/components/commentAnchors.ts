import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { Node as PMNode } from "@tiptap/pm/model";

export type CommentAnchor = {
  id: string;
  from: number;
  to: number;
  status?: string;
};

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    commentAnchors: {
      setCommentAnchors: (anchors: CommentAnchor[]) => ReturnType;
    };
  }
}

type PluginState = { anchors: CommentAnchor[]; decos: DecorationSet };

const commentAnchorsKey = new PluginKey<PluginState>("commentAnchors");

function buildDecorations(doc: PMNode, anchors: CommentAnchor[]) {
  const decos = [];
  const size = doc.content.size;
  for (const a of anchors) {
    if (a.from == null || a.to == null || a.from >= a.to) continue;
    const from = Math.max(1, Math.min(a.from, size));
    const to = Math.max(from + 1, Math.min(a.to, size + 1));
    if (from >= to) continue;
    const unresolved = a.status === "unresolved";
    try {
      decos.push(
        Decoration.inline(from, to, {
          class: unresolved ? "pm-comment-anchor pm-comment-anchor-unresolved" : "pm-comment-anchor",
          "data-comment-id": a.id,
        }),
      );
    } catch {
      /* invalid range for current doc skip */
    }
  }
  return DecorationSet.create(doc, decos);
}

/** Soft yellow highlights for Final comment ranges (PLAN.md P1). */
export const CommentAnchors = Extension.create({
  name: "commentAnchors",

  addOptions() {
    return { anchors: [] as CommentAnchor[] };
  },

  addCommands() {
    return {
      setCommentAnchors:
        (anchors: CommentAnchor[]) =>
        ({ tr, dispatch }) => {
          this.options.anchors = anchors;
          if (dispatch) {
            tr.setMeta(commentAnchorsKey, { anchors });
            dispatch(tr);
          }
          return true;
        },
    };
  },

  addProseMirrorPlugins() {
    // The ProseMirror plugin callbacks below are plain functions with their own
    // `this`, so the extension has to be captured here - this is TipTap's own
    // documented pattern, not an accidental alias.
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const ext = this;
    return [
      new Plugin<PluginState>({
        key: commentAnchorsKey,
        state: {
          init: (_, state) => ({
            anchors: ext.options.anchors,
            decos: buildDecorations(state.doc, ext.options.anchors),
          }),
          apply(tr, prev, _old, state) {
            const meta = tr.getMeta(commentAnchorsKey) as { anchors?: CommentAnchor[] } | undefined;
            const anchors = meta?.anchors ?? prev.anchors ?? ext.options.anchors;
            if (meta?.anchors || tr.docChanged) {
              return { anchors, decos: buildDecorations(state.doc, anchors) };
            }
            return {
              anchors,
              decos: prev.decos.map(tr.mapping, tr.doc),
            };
          },
        },
        props: {
          decorations(state) {
            return commentAnchorsKey.getState(state)?.decos;
          },
        },
      }),
    ];
  },
});
