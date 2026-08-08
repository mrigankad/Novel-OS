import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { Editor } from "@tiptap/react";
import Icon from "./Icon";

/** Floating labeled menu when text is selected (left-click drag) in Final. */
export default function SelectionBubble({
  editor,
  onComment,
  onLinkCodex,
  onCreateCodex,
  onRewrite,
  onAskScribe,
}: {
  editor: Editor | null;
  onComment: () => void;
  onLinkCodex: () => void;
  onCreateCodex: () => void;
  onRewrite?: () => void;
  onAskScribe?: () => void;
}) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    if (!editor) return;

    const update = () => {
      const { from, to, empty } = editor.state.selection;
      if (empty || from === to || !editor.isEditable) {
        setPos(null);
        return;
      }
      const start = editor.view.coordsAtPos(from);
      const end = editor.view.coordsAtPos(to);
      const left = (start.left + end.right) / 2;
      const top = Math.min(start.top, end.top) - 10;
      setPos({ top, left });
    };

    editor.on("selectionUpdate", update);
    editor.on("blur", () => {
      requestAnimationFrame(() => {
        if (!editor.view.hasFocus()) setPos(null);
      });
    });
    editor.on("focus", update);
    window.addEventListener("scroll", update, true);
    return () => {
      editor.off("selectionUpdate", update);
      editor.off("blur", update);
      editor.off("focus", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [editor]);

  return (
    <AnimatePresence>
      {pos && (
        <motion.div
          initial={{ opacity: 0, y: 6, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 4, scale: 0.96 }}
          transition={{ duration: 0.16 }}
          style={{ top: pos.top, left: pos.left, transform: "translate(-50%, -100%)" }}
          className="pointer-events-auto fixed z-[70] flex max-w-[min(92vw,420px)] flex-wrap items-center gap-0.5 rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/95 p-1 shadow-[0_16px_36px_rgba(40,52,90,0.18)] backdrop-blur-md"
          onMouseDown={(e) => e.preventDefault()}
        >
          {onRewrite && (
            <MenuBtn label="Rewrite with AI" primary onClick={onRewrite}>
              <Icon name="sparkles" className="h-3.5 w-3.5" />
            </MenuBtn>
          )}
          {onAskScribe && (
            <MenuBtn label="Ask Scribe" onClick={onAskScribe}>
              <Icon name="message-square" className="h-3.5 w-3.5" />
            </MenuBtn>
          )}
          <MenuBtn label="Comment" onClick={onComment}>
            <Icon name="message-square" className="h-3.5 w-3.5" />
          </MenuBtn>
          <MenuBtn label="Link Codex" onClick={onLinkCodex}>
            <Icon name="users" className="h-3.5 w-3.5" />
          </MenuBtn>
          <MenuBtn label="New entry" onClick={onCreateCodex}>
            <Icon name="plus" className="h-3.5 w-3.5" />
          </MenuBtn>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function MenuBtn({
  children, onClick, label, primary,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
        primary
          ? "bg-[rgba(104,103,234,0.12)] text-[var(--color-violet)] hover:bg-[rgba(104,103,234,0.18)]"
          : "text-ink-muted hover:bg-[rgba(104,103,234,0.08)] hover:text-[var(--color-violet)]"
      }`}
    >
      {children}
      <span>{label}</span>
    </button>
  );
}
