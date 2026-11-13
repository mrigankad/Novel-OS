import { clsx } from "clsx";
import type { TraitRow } from "@/lib/api/voice";

/** Paired bars per trait: You in ink, the draft in gall (red when the gap is large). */
export function TraitBars({ rows, chapter }: { rows: TraitRow[]; chapter: number | null }) {
  return (
    <div>
      <div className="mb-4 flex items-center gap-4 text-[12px] text-body">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-ink" />You</span>
        {chapter != null && (
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-gall" />Ch {chapter} draft</span>
        )}
      </div>
      <ul className="flex flex-col gap-4">
        {rows.map((r) => {
          const max = Math.max(r.you, r.draft, 1e-9);
          const hasDraft = chapter != null;
          return (
            <li key={r.key}>
              <div className="mb-1.5 flex items-baseline justify-between gap-2">
                <span className="text-[13px] font-semibold text-ink">{r.label}</span>
                {hasDraft && r.large && <span className="text-[11px] font-semibold text-fail">Large gap</span>}
              </div>
              <Bar pct={r.you / max} label={r.you_label} className="bg-ink" />
              {hasDraft && (
                <Bar pct={r.draft / max} label={r.draft_label} className={r.large ? "bg-fail" : "bg-gall"}
                  labelClass={r.large ? "text-fail" : "text-gall"} />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Bar({ pct, label, className, labelClass }: { pct: number; label: string; className: string; labelClass?: string }) {
  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-sheet">
        <div className={clsx("h-full rounded-full transition-[width] duration-500", className)}
          style={{ width: `${Math.max(2, Math.round(pct * 100))}%` }} />
      </div>
      <span className={clsx("w-16 shrink-0 text-right text-[12px] tabular-nums text-body", labelClass)}>{label}</span>
    </div>
  );
}
