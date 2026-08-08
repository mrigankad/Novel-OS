import type { ReactNode } from "react";
import Icon, { type IconName } from "./Icon";

export type ChoiceOption<T extends string = string> = {
  value: T;
  label: string;
  icon?: IconName;
  hint?: string;
  /** Custom face for the option (e.g. font sample). */
  preview?: ReactNode;
};

/**
 * Exclusive choice for small closed sets.
 * Prefer this over Select when options are ≤ ~8 and mean something at a glance.
 */
export default function ChoiceGroup<T extends string>({
  label,
  value,
  onChange,
  options,
  variant = "chips",
  size = "md",
  className = "",
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: ChoiceOption<T>[];
  variant?: "chips" | "segmented" | "cards";
  size?: "sm" | "md";
  className?: string;
}) {
  if (variant === "segmented") {
    return (
      <div
        role="radiogroup"
        aria-label={label}
        className={`inline-flex overflow-hidden rounded-full border border-paper-line bg-[var(--color-surface-warm)] p-0.5 ${className}`}
      >
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={o.label}
              title={o.label}
              onClick={() => onChange(o.value)}
              className={`${
                size === "sm" ? "px-2.5 py-1 text-[11.5px]" : "px-3 py-1.5 text-[12.5px]"
              } rounded-full font-medium transition-colors ${
                on ? "bg-ink text-on-ink" : "text-ink-muted hover:text-ink"
              }`}
            >
              {o.preview ?? o.label}
            </button>
          );
        })}
      </div>
    );
  }

  if (variant === "cards") {
    return (
      <div role="radiogroup" aria-label={label} className={`grid grid-cols-2 gap-2 sm:grid-cols-4 ${className}`}>
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(o.value)}
              className={`flex flex-col items-start gap-1.5 rounded-2xl border px-3 py-3 text-left transition-all ${
                on
                  ? "border-[rgba(104,103,234,0.45)] bg-[rgba(238,237,255,0.85)] shadow-[0_8px_20px_rgba(104,103,234,0.1)]"
                  : "border-[rgba(74,91,133,0.12)] bg-white/55 hover:border-[rgba(104,103,234,0.28)]"
              }`}
            >
              {o.icon && (
                <Icon
                  name={o.icon}
                  className={`h-4 w-4 ${on ? "text-[var(--color-violet)]" : "text-ink-muted"}`}
                />
              )}
              <span className={`text-[13px] font-semibold tracking-[-0.01em] ${on ? "text-ink-text" : "text-ink-muted"}`}>
                {o.label}
              </span>
              {o.hint && <span className="text-[11px] leading-snug text-paper-muted">{o.hint}</span>}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div role="radiogroup" aria-label={label} className={`flex flex-wrap gap-1.5 ${className}`}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-full font-medium transition-colors ${
              size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3 py-1.5 text-[12.5px]"
            } ${
              on
                ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                : "border border-[rgba(96,112,153,0.16)] bg-white/55 text-ink-muted hover:text-ink"
            }`}
          >
            {o.icon && <Icon name={o.icon} className="h-3.5 w-3.5" />}
            {o.preview ?? o.label}
          </button>
        );
      })}
    </div>
  );
}
