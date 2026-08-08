import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";

export type ContextMenuItem = {
  id: string;
  label: string;
  hint?: string;
  disabled?: boolean;
  danger?: boolean;
  onSelect: () => void;
};

/** Shared right-click / positioned action menu (R0). */
export default function ContextMenu({
  open,
  x,
  y,
  items,
  onClose,
}: {
  open: boolean;
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  // Keep menu inside viewport
  const left = Math.min(x, typeof window !== "undefined" ? window.innerWidth - 220 : x);
  const top = Math.min(y, typeof window !== "undefined" ? window.innerHeight - 200 : y);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={ref}
          role="menu"
          initial={{ opacity: 0, scale: 0.96, y: -4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: -4 }}
          transition={{ duration: 0.15 }}
          style={{ left, top }}
          className="fixed z-[80] min-w-[200px] overflow-hidden rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/95 p-1 shadow-[0_18px_40px_rgba(40,52,90,0.18)] backdrop-blur-md"
          onMouseDown={(e) => e.preventDefault()}
        >
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                if (item.disabled) return;
                item.onSelect();
                onClose();
              }}
              className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-[13px] font-medium transition-colors disabled:opacity-40 ${
                item.danger
                  ? "text-[#c85177] hover:bg-[#ffeaf1]"
                  : "text-ink-text hover:bg-[rgba(104,103,234,0.08)]"
              }`}
            >
              <span>{item.label}</span>
              {item.hint && <span className="text-[11px] text-ink-muted">{item.hint}</span>}
            </button>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
