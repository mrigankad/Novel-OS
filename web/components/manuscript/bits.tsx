import { clsx } from "clsx";

/** planned: hollow ring · drafting/drafted/revising: ink · final: gall. */
export function StatusDot({ status, className }: { status: string; className?: string }) {
  const style =
    status === "final" ? "bg-gall border-gall"
      : status === "planned" ? "bg-transparent border-rule-strong"
        : status === "drafting" ? "bg-body border-body"
          : "bg-ink border-ink";
  return (
    <span
      title={status}
      aria-label={status}
      className={clsx("inline-block h-2.5 w-2.5 shrink-0 rounded-full border-[1.5px]", style, className)}
    />
  );
}

export function ProgressBar({ value, max, className }: { value: number; max: number; className?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={clsx("h-1 w-full overflow-hidden rounded-full bg-rule", className)} role="progressbar"
      aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-ink transition-[width] duration-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

export const fmt = (n: number) => n.toLocaleString();
