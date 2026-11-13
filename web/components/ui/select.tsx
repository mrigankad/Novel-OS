"use client";

import { clsx } from "clsx";
import { Check, ChevronDown } from "lucide-react";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

export interface SelectOption<V extends string | number = string> {
  value: V;
  label: string;
  /** Leading visual: a BrandIcon, a lucide icon, a status dot. */
  icon?: ReactNode;
  /** Secondary line under the label. */
  hint?: string;
  disabled?: boolean;
}

/**
 * The studio's dropdown. Replaces native <select> so menus match the design in
 * both themes, can show provider marks and hints, and stay fully keyboard
 * accessible (listbox pattern: arrows, Home/End, type-ahead, Enter, Escape).
 */
export function Select<V extends string | number = string>({
  value, onChange, options, placeholder = "Choose…", disabled, size = "md", className, menuClassName,
  "aria-label": ariaLabel, id,
}: {
  value: V | null | undefined;
  onChange: (value: V) => void;
  options: SelectOption<V>[];
  placeholder?: string;
  disabled?: boolean;
  size?: "sm" | "md";
  className?: string;
  menuClassName?: string;
  "aria-label"?: string;
  id?: string;
}) {
  const uid = useId();
  const listId = `${uid}-list`;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [up, setUp] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: "", at: 0 });

  const selectedIndex = options.findIndex((o) => o.value === value);
  const selected = selectedIndex >= 0 ? options[selectedIndex] : null;

  const step = useCallback((from: number, dir: 1 | -1) => {
    for (let i = 1; i <= options.length; i++) {
      const j = (from + dir * i + options.length) % options.length;
      if (!options[j].disabled) return j;
    }
    return from;
  }, [options]);

  const openMenu = () => {
    if (disabled) return;
    setActive(selectedIndex >= 0 ? selectedIndex : step(-1, 1));
    setOpen(true);
  };
  const close = (focusButton = true) => {
    setOpen(false);
    if (focusButton) button.current?.focus();
  };
  const choose = (i: number) => {
    const o = options[i];
    if (!o || o.disabled) return;
    onChange(o.value);
    close();
  };

  // Open upward when there isn't room below.
  useLayoutEffect(() => {
    if (!open || !button.current) return;
    const r = button.current.getBoundingClientRect();
    setUp(window.innerHeight - r.bottom < 300 && r.top > window.innerHeight - r.bottom);
  }, [open]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) close(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // Keep the active option in view.
  useEffect(() => {
    if (open && active >= 0) list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [open, active]);

  const onKey = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); openMenu(); }
      return;
    }
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); setActive((a) => step(a, 1)); break;
      case "ArrowUp": e.preventDefault(); setActive((a) => step(a, -1)); break;
      case "Home": e.preventDefault(); setActive(step(-1, 1)); break;
      case "End": e.preventDefault(); setActive(step(options.length, -1)); break;
      case "Enter": case " ": e.preventDefault(); choose(active); break;
      case "Escape": e.preventDefault(); close(); break;
      case "Tab": close(false); break;
      default:
        if (e.key.length === 1 && /\S/.test(e.key)) {
          const now = Date.now();
          typed.current = { text: (now - typed.current.at < 600 ? typed.current.text : "") + e.key.toLowerCase(), at: now };
          const hit = options.findIndex((o) => !o.disabled && o.label.toLowerCase().startsWith(typed.current.text));
          if (hit >= 0) setActive(hit);
        }
    }
  };

  return (
    <div ref={root} className={clsx("relative", className)}>
      <button
        ref={button}
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={ariaLabel}
        aria-activedescendant={open && active >= 0 ? `${uid}-o${active}` : undefined}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onKey}
        className={clsx(
          "flex w-full items-center gap-2 rounded-[10px] border bg-paper text-left text-ink transition-colors",
          "disabled:cursor-not-allowed disabled:opacity-50",
          open ? "border-gall" : "border-rule-strong hover:border-body",
          size === "sm" ? "h-8 px-2.5 text-[13px]" : "h-10 px-3 text-[14px]",
        )}
      >
        {selected?.icon && <span className="flex shrink-0 items-center">{selected.icon}</span>}
        <span className={clsx("min-w-0 flex-1 truncate", !selected && "text-muted")}>{selected?.label ?? placeholder}</span>
        <ChevronDown size={16} strokeWidth={1.75} aria-hidden
          className={clsx("shrink-0 text-muted transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <ul
          ref={list}
          id={listId}
          role="listbox"
          aria-label={ariaLabel}
          tabIndex={-1}
          onKeyDown={onKey}
          className={clsx(
            "absolute left-0 z-50 max-h-[300px] min-w-full overflow-y-auto rounded-[12px] bg-paper p-1",
            "shadow-[0_12px_32px_rgba(20,19,26,0.16)] ring-1 ring-rule",
            up ? "bottom-full mb-1.5" : "top-full mt-1.5",
            menuClassName,
          )}
        >
          {options.length === 0 && <li className="px-3 py-2 text-[13px] text-muted">Nothing to choose yet</li>}
          {options.map((o, i) => {
            const isSel = i === selectedIndex;
            return (
              <li
                key={String(o.value)}
                id={`${uid}-o${i}`}
                data-i={i}
                role="option"
                aria-selected={isSel}
                aria-disabled={o.disabled || undefined}
                onMouseEnter={() => !o.disabled && setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(i)}
                className={clsx(
                  "flex cursor-pointer items-center gap-2.5 rounded-[8px] px-2.5 py-2 text-[14px]",
                  i === active && !o.disabled && "bg-sheet",
                  o.disabled ? "cursor-not-allowed text-muted" : "text-ink",
                )}
              >
                {o.icon && <span className="flex shrink-0 items-center">{o.icon}</span>}
                <span className="min-w-0 flex-1">
                  <span className={clsx("block truncate", isSel && "font-semibold")}>{o.label}</span>
                  {o.hint && <span className="block truncate text-[12px] text-muted">{o.hint}</span>}
                </span>
                <Check size={15} strokeWidth={2} aria-hidden className={clsx("shrink-0 text-gall", !isSel && "invisible")} />
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
