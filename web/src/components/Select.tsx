import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Icon from "./Icon";

export type SelectOption = { value: string; label: string };

export default function Select({
  value,
  onChange,
  options,
  id,
  label,
  className = "",
  size = "md",
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  id?: string;
  label?: string;
  className?: string;
  size?: "sm" | "md";
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const selected = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const trigger =
    size === "sm"
      ? "inline-flex h-8 min-w-[7.5rem] items-center justify-between gap-2 rounded-full border border-[rgba(96,112,153,0.16)] bg-white/70 px-3 text-[12px] font-medium text-ink-muted transition-colors hover:text-ink"
      : "flex w-full items-center justify-between gap-3 rounded-full border border-[rgba(96,112,153,0.17)] bg-white/60 px-4 py-2.5 text-[14px] font-medium text-ink-text shadow-[inset_0_1px_3px_rgba(48,62,98,0.06)] transition-[border-color,box-shadow,background] hover:bg-white focus:border-[rgba(104,103,234,0.38)] focus:bg-white focus:outline-none focus:shadow-[0_0_0_5px_rgba(104,103,234,0.09)]";

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        id={id}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        className={`${trigger} disabled:opacity-40`}
      >
        <span className="truncate text-left">{selected?.label ?? value}</span>
        <Icon
          name="chevron-right"
          className={`h-3.5 w-3.5 shrink-0 text-ink-muted transition-transform duration-200 ${
            open ? "-rotate-90" : "rotate-90"
          }`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            id={listId}
            role="listbox"
            aria-label={label}
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
            className="absolute left-0 right-0 z-[70] mt-2 max-h-56 overflow-y-auto rounded-2xl border border-[rgba(74,91,133,0.12)] bg-white/95 p-1.5 shadow-[0_18px_40px_rgba(34,77,151,0.16)] backdrop-blur-xl"
          >
            {options.map((o) => {
              const active = o.value === value;
              return (
                <li key={o.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onChange(o.value);
                      setOpen(false);
                    }}
                    className={`flex w-full items-center rounded-xl px-3 py-2.5 text-left text-[13.5px] transition-colors ${
                      active
                        ? "bg-[rgba(104,103,234,0.12)] font-medium text-[var(--color-violet)]"
                        : "text-ink-text hover:bg-[rgba(74,91,133,0.06)]"
                    }`}
                  >
                    {o.label}
                  </button>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
