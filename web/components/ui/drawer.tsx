"use client";

import { clsx } from "clsx";
import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal slide-over: left, right, or bottom sheet. Closes on Escape and on the
 * scrim, traps focus while open, and returns focus to whatever opened it.
 */
export function Drawer({
  open, onClose, side = "left", label, children, className, width = "w-[min(340px,88vw)]", showClose = true,
}: {
  open: boolean; onClose: () => void; side?: "left" | "right" | "bottom"; label: string;
  children: ReactNode; className?: string; showClose?: boolean;
  /** Width class for side drawers. */
  width?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const el = panel.current;
    const first = el?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? el)?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); closeRef.current(); return; }
      if (e.key !== "Tab" || !el) return;
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.offsetParent !== null || n === document.activeElement);
      if (!items.length) { e.preventDefault(); return; }
      const a = items[0], b = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === a || !el.contains(document.activeElement))) { e.preventDefault(); b.focus(); }
      else if (!e.shiftKey && document.activeElement === b) { e.preventDefault(); a.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className={clsx("fixed inset-0 z-50 flex", side === "right" ? "justify-end" : side === "bottom" ? "items-end" : "justify-start")}>
      <button type="button" aria-label="Close" tabIndex={-1} className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={clsx(
          "relative flex flex-col overflow-y-auto bg-paper shadow-[0_12px_40px_rgba(0,0,0,0.24)] outline-none",
          "motion-safe:animate-[drawer-in_180ms_var(--ease-out)]",
          side === "bottom" ? "max-h-[85vh] w-full rounded-t-[16px]" : clsx("h-full", width),
          side === "left" && "[--drawer-from:-100%_0]",
          side === "right" && "[--drawer-from:100%_0]",
          side === "bottom" && "[--drawer-from:0_100%]",
          className,
        )}
      >
        <style>{"@keyframes drawer-in { from { translate: var(--drawer-from); } to { translate: 0 0; } }"}</style>
        {showClose && (
          <button type="button" onClick={onClose} aria-label="Close panel"
            className="absolute right-3 top-3 z-10 rounded-[8px] p-2 text-muted hover:bg-sheet hover:text-ink">
            <X className="h-4 w-4" strokeWidth={1.75} />
          </button>
        )}
        {children}
      </div>
    </div>
  );
}
