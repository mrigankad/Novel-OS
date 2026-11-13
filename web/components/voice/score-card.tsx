import Link from "next/link";
import { clsx } from "clsx";
import { ArrowRight } from "lucide-react";
import type { Lift, VoiceMatch } from "@/lib/api/voice";

export function ScoreCard({ projectId, match, loading }: { projectId: string; match?: VoiceMatch; loading?: boolean }) {
  return (
    <div className="rounded-[16px] bg-wash p-6">
      {match ? (
        <>
          <p className="font-display text-[72px] font-bold leading-none tracking-[-0.04em] text-gall tabular-nums">
            {match.score}%
          </p>
          <p className="mt-2 text-[13px] font-semibold text-ink">Ch {match.chapter} draft vs. you</p>
          {match.gaps.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-2">
              {match.gaps.map((g) => <li key={g} className="text-[14px] leading-relaxed text-ink">{g}</li>)}
            </ul>
          ) : (
            <p className="mt-4 text-[14px] text-ink">This draft sounds like you.</p>
          )}
          <Link href={`/p/${projectId}/room`}
            className="mt-5 inline-flex items-center gap-1.5 text-[14px] font-semibold text-gall hover:text-gall-hover">
            Ask Scribe to rebalance <ArrowRight size={15} strokeWidth={1.75} />
          </Link>
        </>
      ) : (
        <p className="text-[14px] text-ink">
          {loading ? "Measuring the draft..." : "Draft a chapter, then pick it above to see how close it sounds to you."}
        </p>
      )}
    </div>
  );
}

const LIFTS: { value: Lift; label: string; hint: string }[] = [
  { value: "pure_me", label: "Pure me", hint: "Agents match you exactly." },
  { value: "me_plus_lift", label: "Me + lift", hint: "Your voice, with borrowed craft for tension and openings." },
  { value: "experiment", label: "Experiment", hint: "Push stylistic range; POV and tense stay fixed." },
];

export function LiftControl({ value, onChange, disabled }: { value: Lift; onChange: (l: Lift) => void; disabled?: boolean }) {
  const hint = LIFTS.find((l) => l.value === value)?.hint;
  return (
    <div>
      <h3 className="label mb-3">Lift</h3>
      <div role="radiogroup" aria-label="Lift" className="grid grid-cols-3 rounded-[10px] bg-sheet p-1">
        {LIFTS.map((l) => (
          <button key={l.value} type="button" role="radio" aria-checked={value === l.value} disabled={disabled}
            onClick={() => onChange(l.value)}
            className={clsx("h-8 rounded-[7px] text-[13px] font-semibold transition-colors",
              value === l.value ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.12)]" : "text-body hover:text-ink")}>
            {l.label}
          </button>
        ))}
      </div>
      {hint && <p className="mt-2 text-[12px] text-body">{hint}</p>}
    </div>
  );
}
