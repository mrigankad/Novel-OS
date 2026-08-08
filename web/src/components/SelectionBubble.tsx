import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { Editor } from "@tiptap/react";
import Icon from "./Icon";
import type { SelectionAction, SelectionActionId } from "../lib/selectionActions";

/**
 * The single AI entry point (design spec §4.6).
 *
 * Appears only when text is selected, shows only the actions that change the
 * manuscript, and never volunteers anything on its own - no ghost text, no
 * hovering suggestion mid-sentence. The loudest complaint about the
 * best-funded tool in this category is that it "never really disappears";
 * this bar exists so that the rest of the writing surface can.
 *
 * The actions come from `lib/selectionActions` so the bar and the right-click
 * menu can never offer different things.
 */
export default function SelectionBubble({
  editor,
  actions,
  onSelect,
}: {
  editor: Editor | null;
  actions: readonly SelectionAction[];
  onSelect: (id: SelectionActionId) => void;
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
      setPos({
        left: (start.left + end.right) / 2,
        top: Math.min(start.top, end.top) - 10,
      });
    };

    const onBlur = () => {
      // A click on the bar itself blurs the editor; only hide once focus has
      // genuinely gone elsewhere, or the bar disappears as you reach for it.
      requestAnimationFrame(() => {
        if (!editor.view.hasFocus()) setPos(null);
      });
    };

    editor.on("selectionUpdate", update);
    editor.on("blur", onBlur);
    editor.on("focus", update);
    window.addEventListener("scroll", update, true);
    return () => {
      editor.off("selectionUpdate", update);
      editor.off("blur", onBlur);
      editor.off("focus", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [editor]);

  if (actions.length === 0) return null;

  return (
    <AnimatePresence>
      {pos && (
        <motion.div
          role="toolbar"
          aria-label="Selection actions"
          initial={{ opacity: 0, y: 6, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 4, scale: 0.96 }}
          transition={{ duration: 0.16 }}
          style={{ top: pos.top, left: pos.left, transform: "translate(-50%, -100%)" }}
          className="pointer-events-auto fixed z-[70] flex max-w-[min(92vw,420px)] flex-wrap items-center gap-0.5 rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/95 p-1 shadow-[0_16px_36px_rgba(40,52,90,0.18)] backdrop-blur-md"
          // Keep the editor selection alive while the bar is clicked.
          onMouseDown={(e) => e.preventDefault()}
        >
          {actions.map((a) => (
            <button
              key={a.id}
              type="button"
              title={a.label}
              aria-label={a.label}
              onClick={() => onSelect(a.id)}
              className={`inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
                a.id === "rewrite"
                  ? "bg-[rgba(104,103,234,0.12)] text-[var(--color-violet)] hover:bg-[rgba(104,103,234,0.18)]"
                  : "text-ink-muted hover:bg-[rgba(104,103,234,0.08)] hover:text-[var(--color-violet)]"
              }`}
            >
              <Icon name={a.icon} className="h-3.5 w-3.5" />
              <span>{a.label}</span>
            </button>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
