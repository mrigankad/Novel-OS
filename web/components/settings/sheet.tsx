"use client";

import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

/** Right-hand sheet used by "Add connection" and "Try it". */
export function Sheet({
  open, title, eyebrow, onClose, children, footer,
}: {
  open: boolean; title: string; eyebrow?: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/20" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-[440px] flex-col bg-paper shadow-[-12px_0_40px_rgba(20,19,26,0.12)]">
        <header className="flex items-start justify-between gap-4 border-b border-rule px-6 py-5">
          <div>
            {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
            <h2 className="font-display text-[24px] font-bold tracking-[-0.02em] text-ink">{title}</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-[8px] p-1.5 text-body hover:bg-sheet hover:text-ink">
            <X size={18} strokeWidth={1.75} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-rule px-6 py-4">{footer}</footer>}
      </aside>
    </div>
  );
}
