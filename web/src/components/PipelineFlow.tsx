import type { ChapterStages } from "../api/client";

export type StageKey = "outline" | "draft" | "revised" | "final";

const STAGES: { key: StageKey; label: string; agent: string }[] = [
  { key: "outline", label: "Outline", agent: "Architect" },
  { key: "draft", label: "Draft", agent: "Scribe" },
  { key: "revised", label: "Revised", agent: "Editor" },
  { key: "final", label: "Final", agent: "You" },
];

export default function PipelineFlow({
  stages,
  selected,
  onSelect,
}: {
  stages: ChapterStages;
  selected: StageKey;
  onSelect: (s: StageKey) => void;
}) {
  return (
    <div className="flex items-stretch gap-1">
      {STAGES.map((s, i) => {
        const present = stages[s.key] != null;
        const isSel = selected === s.key;
        const isFinal = s.key === "final";
        return (
          <div key={s.key} className="flex flex-1 items-center">
            <button
              onClick={() => onSelect(s.key)}
              className={`group flex w-full flex-col items-start rounded-lg border px-3.5 py-2.5 text-left transition-all ${
                isSel
                  ? isFinal
                    ? "border-amber bg-amber/15 shadow-[var(--shadow-paper)]"
                    : "border-ink/25 bg-ink/[0.04] shadow-[var(--shadow-paper)]"
                  : "border-paper-line bg-paper-card/50 hover:border-ink/20 hover:bg-paper-card"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    present
                      ? isFinal
                        ? "bg-amber-deep"
                        : "bg-st-approved"
                      : "bg-paper-muted/50"
                  }`}
                />
                <span
                  className={`font-display text-[14px] font-semibold tracking-tight ${
                    isSel ? "text-ink-text" : "text-ink-muted"
                  }`}
                >
                  {s.label}
                </span>
              </span>
              <span className="mt-0.5 pl-3 text-[10.5px] uppercase tracking-[0.1em] text-paper-muted">
                {present ? s.agent : "not run"}
              </span>
            </button>
            {i < STAGES.length - 1 && (
              <svg width="20" height="12" viewBox="0 0 20 12" className="shrink-0" aria-hidden>
                <path
                  d="M1 6h15m0 0l-4-4m4 4l-4 4"
                  fill="none"
                  stroke={stages[STAGES[i + 1].key] != null ? "#c98a16" : "#cbc3ad"}
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        );
      })}
    </div>
  );
}
