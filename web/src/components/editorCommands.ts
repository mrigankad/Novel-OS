import { EditorSelection } from "@codemirror/state";
import type { EditorView } from "@uiw/react-codemirror";

/** Wrap each selection range with `before`/`after` (e.g. ** for bold). */
export function surround(view: EditorView, before: string, after = before) {
  const tr = view.state.changeByRange((range) => ({
    changes: [
      { from: range.from, insert: before },
      { from: range.to, insert: after },
    ],
    range: EditorSelection.range(range.from + before.length, range.to + before.length),
  }));
  view.dispatch(view.state.update(tr, { scrollIntoView: true }));
  view.focus();
}

/** Prefix the current line(s) with `prefix` (e.g. "## " for a heading, "> " quote). */
export function prefixLine(view: EditorView, prefix: string) {
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.head);
  view.dispatch(
    state.update({
      changes: { from: line.from, insert: prefix },
      selection: EditorSelection.cursor(state.selection.main.head + prefix.length),
      scrollIntoView: true,
    }),
  );
  view.focus();
}

/** Insert a block of text at the cursor (e.g. a scene break). */
export function insertBlock(view: EditorView, text: string) {
  const pos = view.state.selection.main.to;
  view.dispatch(
    view.state.update({
      changes: { from: pos, insert: text },
      selection: EditorSelection.cursor(pos + text.length),
      scrollIntoView: true,
    }),
  );
  view.focus();
}
