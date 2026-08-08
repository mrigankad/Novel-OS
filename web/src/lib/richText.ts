import type { Editor, JSONContent } from "@tiptap/react";
import type { CommentAnchor } from "../components/commentAnchors";

/** ProseMirror JSON matching `api/richtext.py` - Final's canonical form. */
export type PMDoc = JSONContent & { type: "doc" };

export const EMPTY_DOC: PMDoc = { type: "doc", content: [{ type: "paragraph" }] };

export type EditorHandle = {
  focus: () => void;
  getJSON: () => PMDoc;
  getText: () => string;
  getSelection: () => {
    from: number;
    to: number;
    quote: string;
    before: string;
    after: string;
  } | null;
  setCommentAnchors: (anchors: CommentAnchor[]) => void;
  scrollToAnchor: (from: number, to: number) => void;
  setCodexMention: (entryId: string, entryType: string) => boolean;
  editor: Editor | null;
};

// Toolbar commands. Split from RichTextEditor.tsx so that file exports only a
// component, which is what Fast Refresh needs to hot-swap the editor.

export function toggleBold(h: EditorHandle | null) {
  h?.editor?.chain().focus().toggleBold().run();
}
export function toggleItalic(h: EditorHandle | null) {
  h?.editor?.chain().focus().toggleItalic().run();
}
export function setHeading(h: EditorHandle | null, level: 1 | 2 | 3) {
  h?.editor?.chain().focus().toggleHeading({ level }).run();
}
export function toggleBlockquote(h: EditorHandle | null) {
  h?.editor?.chain().focus().toggleBlockquote().run();
}
export function insertSceneBreak(h: EditorHandle | null) {
  h?.editor?.chain().focus().setHorizontalRule().run();
}
export function insertImage(h: EditorHandle | null, src: string, alt = "") {
  h?.editor?.chain().focus().setImage({ src, alt }).run();
}
