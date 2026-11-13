"use client";

import type { BetaInsights } from "@/lib/api/beta";
import { fmtDuration } from "@/lib/api/beta";
import { ReactionIcon } from "./reactions";

/**
 * Per-chapter drop-off: a track for everyone invited, a light bar for "started"
 * and a solid ink bar for "finished". One hue, labelled directly, no legend hunt.
 */
export function Dropoff({ data }: { data: BetaInsights }) {
  const max = Math.max(1, data.readers);
  const time = new Map(data.reading_time.map((r) => [r.chapter, r.avg_seconds]));
  const title = new Map(data.chapters.map((c) => [c.number, c.title]));
  return (
    <figure>
      <figcaption className="mb-3 text-[13px] text-body">
        Of {data.readers} reader{data.readers === 1 ? "" : "s"}: <span className="font-semibold text-ink">finished</span> /
        <span className="text-muted"> started</span> each chapter, and average time spent.
      </figcaption>
      <div className="flex flex-col gap-2">
        {data.dropoff.map((d) => (
          <div key={d.chapter} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-[13px]">
            <span className="truncate text-body" title={title.get(d.chapter)}>
              <span className="text-muted">{d.chapter}</span> {title.get(d.chapter) || `Chapter ${d.chapter}`}
            </span>
            <div className="relative h-3 rounded-full bg-sheet" role="img"
              aria-label={`Chapter ${d.chapter}: ${d.finished} finished, ${d.started} started of ${data.readers}`}>
              <div className="absolute inset-y-0 left-0 rounded-full bg-rule-strong" style={{ width: `${(d.started / max) * 100}%` }} />
              <div className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${(d.finished / max) * 100}%` }} />
            </div>
            <span className="w-28 text-right tabular-nums text-body">
              <span className="font-semibold text-ink">{d.finished}</span>
              <span className="text-muted"> / {d.started}</span>
              <span className="ml-2 text-muted">{fmtDuration(time.get(d.chapter) ?? 0)}</span>
            </span>
          </div>
        ))}
      </div>
    </figure>
  );
}

/** Density of notes and reactions through each chapter, in tenths. Darker = more. */
export function HeatStrip({ data }: { data: BetaInsights }) {
  const max = Math.max(1, ...data.heat.flatMap((h) => h.total));
  return (
    <figure>
      <figcaption className="mb-3 text-[13px] text-body">Where readers stopped to note or react, start to end of each chapter.</figcaption>
      <div className="flex flex-col gap-1.5">
        {data.heat.map((h) => {
          const sum = h.total.reduce((a, b) => a + b, 0);
          return (
            <div key={h.chapter} className="grid grid-cols-[2rem_1fr_3rem] items-center gap-3 text-[13px]">
              <span className="text-muted">{h.chapter}</span>
              <div className="grid grid-cols-10 gap-[2px]">
                {h.total.map((v, i) => (
                  <div key={i} className="h-5 rounded-[3px] bg-sheet" title={`${i * 10}–${i * 10 + 10}%: ${v}`}
                    style={v ? { background: `color-mix(in srgb, var(--color-ink) ${Math.round(12 + (v / max) * 78)}%, transparent)` } : undefined} />
                ))}
              </div>
              <span className="text-right tabular-nums text-body">{sum || ""}</span>
            </div>
          );
        })}
        <div className="grid grid-cols-[2rem_1fr_3rem] gap-3 text-[11px] text-muted">
          <span /><div className="flex justify-between"><span>start</span><span>end</span></div><span />
        </div>
      </div>
    </figure>
  );
}

export function Confused({ data }: { data: BetaInsights }) {
  if (!data.confused.length) return <p className="text-[14px] text-muted">No confused reactions yet.</p>;
  return (
    <ol className="flex flex-col gap-3">
      {data.confused.map((c) => (
        <li key={`${c.chapter}-${c.quote}`} className="flex gap-3">
          <ReactionIcon reaction="confused" className="mt-1 h-4 w-4 shrink-0 text-body" />
          <div className="min-w-0">
            <p className="font-prose text-[16px] italic leading-[1.5] text-prose">&ldquo;{c.quote}&rdquo;</p>
            <p className="mt-0.5 text-[12px] text-muted">Chapter {c.chapter} · {c.count} reader{c.count === 1 ? "" : "s"}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
