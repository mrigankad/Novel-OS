"use client";

import { clsx } from "clsx";
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useSyncExternalStore } from "react";
import { getThemeChoice, setThemeChoice, subscribeTheme, type ThemeChoice } from "@/lib/theme";

export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(subscribeTheme, getThemeChoice, () => "system");
}

const OPTIONS: { id: ThemeChoice; label: string; icon: LucideIcon }[] = [
  { id: "system", label: "System", icon: Monitor },
  { id: "light", label: "Light", icon: Sun },
  { id: "dark", label: "Dark", icon: Moon },
];

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const choice = useThemeChoice();
  if (compact) {
    const i = OPTIONS.findIndex((o) => o.id === choice);
    const nextOpt = OPTIONS[(i + 1) % OPTIONS.length];
    const Icon = OPTIONS[i].icon;
    return (
      <button type="button" onClick={() => setThemeChoice(nextOpt.id)}
        aria-label={`Theme: ${OPTIONS[i].label}. Switch to ${nextOpt.label}`} title={`Theme: ${OPTIONS[i].label}`}
        className="flex h-9 w-9 items-center justify-center rounded-[8px] text-body transition-colors hover:bg-paper hover:text-ink">
        <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </button>
    );
  }
  return (
    <div role="radiogroup" aria-label="Theme" className="flex rounded-[10px] border border-rule bg-paper p-0.5">
      {OPTIONS.map(({ id, label, icon: Icon }) => (
        <button key={id} type="button" role="radio" aria-checked={choice === id} onClick={() => setThemeChoice(id)}
          className={clsx("flex h-7 flex-1 items-center justify-center gap-1.5 rounded-[8px] text-[12px] font-medium transition-colors",
            choice === id ? "bg-sheet text-ink shadow-[0_0_0_1px_var(--color-rule)]" : "text-muted hover:text-ink")}>
          <Icon className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
          {label}
        </button>
      ))}
    </div>
  );
}
