import { clsx } from "clsx";
import { createElement } from "react";
import {
  Bot, Compass, Feather, Palette, PenLine, ShieldAlert, Telescope, type LucideIcon,
} from "lucide-react";

export const ROLE_ICON: Record<string, LucideIcon> = {
  architect: Compass,
  scribe: PenLine,
  editor: Feather,
  guardian: ShieldAlert,
  curator: Palette,
  researcher: Telescope,
};

export function roleIcon(role: string | undefined): LucideIcon {
  return (role && ROLE_ICON[role]) || Bot;
}

/** Glyph-like lucide icon in a soft tile. */
export function AgentGlyph({ role, size = "md", tone = "soft" }: {
  role?: string; size?: "sm" | "md"; tone?: "soft" | "fail" | "ink";
}) {
  const iconClass = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  return (
    <span className={clsx(
      "inline-flex shrink-0 items-center justify-center rounded-[10px]",
      size === "sm" ? "h-7 w-7" : "h-9 w-9",
      tone === "fail" ? "bg-[color-mix(in_srgb,var(--color-fail)_10%,transparent)] text-fail"
        : tone === "ink" ? "bg-inverse text-on-inverse" : "bg-wash text-gall",
    )}>
      {createElement(roleIcon(role), { className: iconClass, strokeWidth: 1.75 })}
    </span>
  );
}
