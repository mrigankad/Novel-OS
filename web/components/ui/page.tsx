import { clsx } from "clsx";
import type { ReactNode } from "react";

/** Standard screen header: eyebrow, Swiss-scale title, one-line description, actions. */
export function PageHeader({
  eyebrow, title, description, actions,
}: { eyebrow?: string; title: ReactNode; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="font-display text-[40px] font-bold leading-[1.05] tracking-[-0.03em] text-ink">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[15px] text-body">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Page({ children, wide, className }: { children: ReactNode; wide?: boolean; className?: string }) {
  return (
    <div className={clsx("mx-auto px-6 py-10 sm:px-12", wide ? "max-w-[1400px]" : "max-w-5xl", className)}>
      {children}
    </div>
  );
}

export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={clsx("label mt-10 mb-3", className)}>{children}</h2>;
}

export function EmptyState({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-[16px] border border-dashed border-rule-strong px-6 py-14 text-center">
      <p className="font-display text-[22px] font-bold tracking-[-0.02em] text-ink">{title}</p>
      {body && <p className="mt-2 max-w-md text-[14px] text-body">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

const TONES = {
  neutral: "bg-sheet text-body",
  ai: "bg-wash text-gall",
  pass: "bg-[color-mix(in_srgb,var(--color-pass)_12%,transparent)] text-pass",
  warn: "bg-[color-mix(in_srgb,var(--color-warn)_12%,transparent)] text-warn",
  fail: "bg-[color-mix(in_srgb,var(--color-fail)_10%,transparent)] text-fail",
} as const;

export function Badge({ tone = "neutral", dot, children }: { tone?: keyof typeof TONES; dot?: boolean; children: ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold", TONES[tone])}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-[10px] bg-sheet", className)} />;
}
