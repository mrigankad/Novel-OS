import { forwardRef } from "react";
import CodeMirror, { EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { search } from "@codemirror/search";

// Editor styled to read like the manuscript page; colors come from CSS vars so it
// adapts to light/dark automatically.
const manuscriptTheme = EditorView.theme({
  "&": { backgroundColor: "transparent", color: "var(--color-ink-text)" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-prose)", lineHeight: "1.85", overflow: "visible" },
  ".cm-content": {
    fontFamily: "var(--font-prose)",
    fontSize: "var(--editor-size, 1.075rem)",
    padding: "0",
    caretColor: "var(--color-amber-deep)",
  },
  ".cm-line": { padding: "0 2px" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--color-amber-deep)", borderLeftWidth: "2px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "color-mix(in srgb, var(--color-amber) 28%, transparent)",
  },
  ".cm-placeholder": { color: "var(--color-paper-muted)" },
});

const MarkdownEditor = forwardRef<ReactCodeMirrorRef, {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}>(({ value, onChange, placeholder }, ref) => {
  return (
    <CodeMirror
      ref={ref}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      theme="none"
      basicSetup={{
        lineNumbers: false,
        foldGutter: false,
        highlightActiveLine: false,
        highlightActiveLineGutter: false,
        drawSelection: true,
        bracketMatching: false,
        indentOnInput: false,
      }}
      extensions={[
        markdown({ base: markdownLanguage }),
        EditorView.lineWrapping,
        search({ top: true }),
        manuscriptTheme,
      ]}
    />
  );
});

MarkdownEditor.displayName = "MarkdownEditor";
export default MarkdownEditor;
