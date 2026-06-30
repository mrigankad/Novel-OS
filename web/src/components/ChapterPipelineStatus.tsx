import {
  PIPELINE_HINTS,
  PIPELINE_LABELS,
  pipelineStepFromSummary,
  type PipelineStep,
} from "../lib/chapterPipeline";

export function ChapterPipelineDot({
  step,
  size = "md",
  className = "",
  labeled = true,
}: {
  step: PipelineStep;
  size?: "sm" | "md";
  className?: string;
  labeled?: boolean;
}) {
  const sz = size === "sm" ? "h-2 w-2" : "h-2.5 w-2.5";
  return (
    <span
      className={`chapter-pipeline-dot ${sz} shrink-0 rounded-full ${className}`}
      data-pipeline={step}
      title={`${PIPELINE_LABELS[step]} — ${PIPELINE_HINTS[step]}`}
      aria-label={labeled ? PIPELINE_LABELS[step] : undefined}
      aria-hidden={labeled ? undefined : true}
    />
  );
}

export default function ChapterPipelineStatus({
  chapter,
  showLabel = true,
  size = "md",
}: {
  chapter: { pipeline_step?: string; status?: string };
  showLabel?: boolean;
  size?: "sm" | "md";
}) {
  const step = pipelineStepFromSummary(chapter);
  return (
    <span className="inline-flex items-center gap-1.5">
      <ChapterPipelineDot step={step} size={size} />
      {showLabel && (
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
          {PIPELINE_LABELS[step]}
        </span>
      )}
    </span>
  );
}

export function ChapterPipelineLegend({ compact = false }: { compact?: boolean }) {
  const steps: PipelineStep[] = ["none", "drafted", "revised", "validated", "approved", "final"];
  return (
    <div
      className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 ${compact ? "text-[10.5px]" : "text-[11px]"}`}
      aria-label="Chapter pipeline legend"
    >
      {steps.map((step) => (
        <span key={step} className="inline-flex items-center gap-1.5 text-ink-muted">
          <ChapterPipelineDot step={step} size="sm" labeled={false} />
          <span>{PIPELINE_LABELS[step]}</span>
        </span>
      ))}
    </div>
  );
}
