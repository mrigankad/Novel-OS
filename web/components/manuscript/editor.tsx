"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor, type JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";
import { type Highlight, SUGGESTION_CLICK, SuggestionHighlights, suggestionCss, suggestionKey } from "./suggestions";

/** Tiptap prose editor. Loaded with next/dynamic (ssr:false) by the writing screen. */

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** Markdown-ish text to editor HTML (used when a chapter has text but no saved doc). */
export function textToHtml(text: string): string {
  return text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((b) => {
      const h = b.match(/^(#{1,3})\s+(.*)$/);
      if (h) return `<h${h[1].length + 1}>${esc(h[2])}</h${h[1].length + 1}>`;
      if (b.startsWith("> ")) return `<blockquote><p>${esc(b.replace(/^>\s?/gm, ""))}</p></blockquote>`;
      if (/^[-*] /.test(b)) return `<ul>${b.split("\n").map((l) => `<li><p>${esc(l.replace(/^[-*]\s+/, ""))}</p></li>`).join("")}</ul>`;
      if (b === "* * *" || b === "---") return "<hr>";
      return `<p>${esc(b).replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

function inline(node: JSONContent): string {
  if (node.type === "text") {
    let t = node.text ?? "";
    for (const m of node.marks ?? []) {
      if (m.type === "bold") t = `**${t}**`;
      else if (m.type === "italic") t = `*${t}*`;
    }
    return t;
  }
  if (node.type === "hardBreak") return "\n";
  return (node.content ?? []).map(inline).join("");
}

/** Editor JSON to the canonical Markdown-ish chapter text. */
export function docToText(doc: JSONContent): string {
  const blocks: string[] = [];
  for (const node of doc.content ?? []) {
    switch (node.type) {
      case "heading": blocks.push(`${"#".repeat(Math.max(1, (node.attrs?.level ?? 2) - 1))} ${inline(node)}`); break;
      case "blockquote": blocks.push((node.content ?? []).map(inline).join("\n").split("\n").map((l) => `> ${l}`).join("\n")); break;
      case "bulletList":
      case "orderedList":
        blocks.push((node.content ?? []).map((li, i) => `${node.type === "orderedList" ? `${i + 1}.` : "-"} ${inline(li)}`).join("\n"));
        break;
      case "horizontalRule": blocks.push("* * *"); break;
      default: blocks.push(inline(node));
    }
  }
  return blocks.filter((b) => b.trim()).join("\n\n");
}

export default function ProseEditor({
  initialDoc, initialText, onChange, placeholder = "Begin the chapter…",
  highlights, activeHighlight = null, onHighlightClick,
}: {
  initialDoc: Record<string, unknown>;
  initialText: string;
  onChange: (doc: JSONContent, text: string) => void;
  placeholder?: string;
  /** Editor suggestions to mark in the prose (track-changes style). */
  highlights?: Highlight[];
  activeHighlight?: string | null;
  onHighlightClick?: (id: string) => void;
}) {
  const hasDoc = initialDoc && (initialDoc as JSONContent).type === "doc";
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [StarterKit.configure({ heading: { levels: [2, 3, 4] } }), Placeholder.configure({ placeholder }), SuggestionHighlights],
    content: hasDoc ? (initialDoc as JSONContent) : textToHtml(initialText),
    editorProps: { attributes: { class: "prose-book outline-none min-h-[60vh] pb-[30vh]", spellcheck: "true" } },
    onUpdate: ({ editor: e }) => {
      const doc = e.getJSON();
      onChange(doc, docToText(doc));
    },
  });
  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.view.dispatch(editor.state.tr.setMeta(suggestionKey, { items: highlights ?? [], active: activeHighlight }));
    if (activeHighlight) {
      editor.view.dom.querySelector(`[data-suggestion-id="${activeHighlight}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [editor, highlights, activeHighlight]);
  useEffect(() => {
    if (!editor || !onHighlightClick) return;
    const dom = editor.view.dom;
    const fn = (e: Event) => onHighlightClick((e as CustomEvent<string>).detail);
    dom.addEventListener(SUGGESTION_CLICK, fn);
    return () => dom.removeEventListener(SUGGESTION_CLICK, fn);
  }, [editor, onHighlightClick]);
  return (
    <>
      <style>{suggestionCss}</style>
      <style>{`
        .prose-book p.is-editor-empty:first-child::before { content: attr(data-placeholder); float: left; height: 0; pointer-events: none; color: var(--color-muted); }
        .prose-book h2, .prose-book h3, .prose-book h4 { font-weight: 600; margin: 1.4em 0 .5em; }
        .prose-book blockquote { border-left: 2px solid var(--color-rule-strong); padding-left: 1em; color: var(--color-body); }
        .prose-book ul { list-style: disc; padding-left: 1.4em; } .prose-book ol { list-style: decimal; padding-left: 1.4em; }
        .prose-book hr { border: 0; text-align: center; margin: 2em 0; } .prose-book hr::after { content: "* * *"; color: var(--color-muted); }
      `}</style>
      <EditorContent editor={editor} />
    </>
  );
}
