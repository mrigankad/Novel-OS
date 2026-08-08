import { useEffect, useRef } from "react";
import { EditorContent, useEditor, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { CommentAnchors, type CommentAnchor } from "./commentAnchors";
import { CodexMention } from "./codexMention";
import { SuggestionDelete, SuggestionInsert, TrackChanges } from "./trackChangesMarks";
import { useLatestRef } from "../hooks/useLatestRef";

import type { EditorHandle, PMDoc } from "../lib/richText";

export type { EditorHandle, PMDoc };

type Props = {
  doc: PMDoc;
  onChange: (doc: PMDoc) => void;
  placeholder?: string;
  editable?: boolean;
  onReady?: (handle: EditorHandle) => void;
  commentAnchors?: CommentAnchor[];
  onContextMenu?: (e: MouseEvent, editor: Editor) => void;
  /** Fired after left-click mouseup when a non-empty selection remains. */
  onSelectionAction?: (clientX: number, clientY: number) => void;
  onMentionClick?: (entryId: string, entryType: string, clientX: number, clientY: number) => void;
  /** Suggest mode: edits become tracked proposals instead of direct changes. */
  suggesting?: boolean;
  /** Name recorded on suggestions made in this session. */
  author?: string;
};

/**
 * TipTap surface for Final (PLAN.md P1). Schema is kept narrow so it
 * round-trips with `api.richtext` agents still read the markdown projection.
 */
export default function RichTextEditor({
  doc, onChange, placeholder = "Write the chapter…", editable = true, onReady,
  commentAnchors = [], onContextMenu, onSelectionAction, onMentionClick,
  suggesting = false, author = "",
}: Props) {
  const skipNext = useRef(false);
  const onContextMenuRef = useLatestRef(onContextMenu);
  const onSelectionActionRef = useLatestRef(onSelectionAction);
  const onMentionClickRef = useLatestRef(onMentionClick);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4, 5, 6] },
        codeBlock: false,
      }),
      Image.configure({ inline: true, allowBase64: false }),
      Link.configure({ openOnClick: false, HTMLAttributes: { class: "pm-link" } }),
      Placeholder.configure({ placeholder }),
      CommentAnchors.configure({ anchors: commentAnchors }),
      CodexMention,
      SuggestionInsert,
      SuggestionDelete,
      TrackChanges.configure({ author }),
    ],
    content: doc,
    editable,
    editorProps: {
      attributes: {
        class: "pm-editor outline-none min-h-[50vh]",
        "aria-label": "Final manuscript",
      },
      handleDOMEvents: {
        click: (_view, event) => {
          const t = event.target as HTMLElement | null;
          const mention = t?.closest?.(".pm-codex-mention") as HTMLElement | null;
          if (mention && onMentionClickRef.current) {
            const id = mention.getAttribute("data-codex-id");
            const type = mention.getAttribute("data-codex-type") || "character";
            if (id) {
              event.preventDefault();
              onMentionClickRef.current(id, type, event.clientX, event.clientY);
              return true;
            }
          }
          return false;
        },
        mouseup: (view, event) => {
          if (event.button !== 0 || !onSelectionActionRef.current) return false;
          const { clientX, clientY } = event;
          // Wait for ProseMirror to commit the selection from this mouseup.
          requestAnimationFrame(() => {
            const sel = view.state.selection;
            if (sel.empty || !view.editable) return;
            onSelectionActionRef.current?.(clientX, clientY);
          });
          return false;
        },
      },
    },
    onUpdate: ({ editor: ed }) => {
      skipNext.current = true;
      onChange(ed.getJSON() as PMDoc);
    },
  });

  // Fix contextmenu to use the actual editor instance
  useEffect(() => {
    if (!editor) return;
    const dom = editor.view.dom;
    const onCtx = (event: MouseEvent) => {
      onContextMenuRef.current?.(event, editor);
    };
    dom.addEventListener("contextmenu", onCtx);
    return () => dom.removeEventListener("contextmenu", onCtx);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    if (skipNext.current) {
      skipNext.current = false;
      return;
    }
    const current = JSON.stringify(editor.getJSON());
    const next = JSON.stringify(doc);
    if (current !== next) {
      editor.commands.setContent(doc, { emitUpdate: false });
    }
  }, [doc, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.commands.setCommentAnchors(commentAnchors);
  }, [editor, commentAnchors]);

  useEffect(() => {
    if (!editor || !onReady) return;
    onReady({
      focus: () => editor.commands.focus(),
      getJSON: () => editor.getJSON() as PMDoc,
      getText: () => editor.getText(),
      getSelection: () => {
        const { from, to } = editor.state.selection;
        if (from === to) return null;
        const doc = editor.state.doc;
        const quote = doc.textBetween(from, to, "\n");
        const before = doc.textBetween(Math.max(0, from - 500), from, "\n");
        const after = doc.textBetween(to, Math.min(doc.content.size, to + 500), "\n");
        return { from, to, quote, before, after };
      },
      setCommentAnchors: (anchors) => editor.commands.setCommentAnchors(anchors),
      scrollToAnchor: (from, to) => {
        editor.chain().focus().setTextSelection({ from, to }).run();
        requestAnimationFrame(() => {
          const mark = editor.view.dom.querySelector(".pm-comment-anchor");
          (mark as HTMLElement | null)?.scrollIntoView({ block: "center", behavior: "smooth" });
        });
      },
      setCodexMention: (entryId, entryType) =>
        editor.chain().focus().setCodexMention({ entryId, entryType }).run(),
      editor,
    });
  }, [editor, onReady]);

  useEffect(() => {
    if (editor) editor.setEditable(editable);
  }, [editor, editable]);

  useEffect(() => {
    editor?.commands.setSuggesting(suggesting);
  }, [editor, suggesting]);

  return <EditorContent editor={editor} />;
}

export type { CommentAnchor };
