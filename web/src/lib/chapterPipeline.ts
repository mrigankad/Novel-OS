/** Pipeline progress for chapter list / binder status lights. */

export type PipelineStep = "none" | "drafted" | "revised" | "validated" | "approved" | "final";

export const PIPELINE_STEPS: PipelineStep[] = [
  "none", "drafted", "revised", "validated", "approved", "final",
];

export const PIPELINE_LABELS: Record<PipelineStep, string> = {
  none: "Needs outline",
  drafted: "Draft",
  revised: "Revised",
  validated: "Validated",
  approved: "Approved",
  final: "Final",
};

export const PIPELINE_HINTS: Record<PipelineStep, string> = {
  none: "No draft yet — plan or outline this chapter",
  drafted: "Draft complete — run Revise next",
  revised: "Revision complete — run Validate next",
  validated: "Validated — run Approve next",
  approved: "Approved — promote or save Final to finish",
  final: "Final manuscript on file",
};

export function pipelineStepFromSummary(c: { pipeline_step?: string; status?: string }): PipelineStep {
  const step = c.pipeline_step?.toLowerCase();
  if (step && PIPELINE_STEPS.includes(step as PipelineStep)) return step as PipelineStep;
  // Without pipeline_step from the API we cannot detect Final files — show best guess only.
  const st = (c.status ?? "").toLowerCase();
  if (st === "validated") return "validated";
  if (st === "edited" || st === "editing") return "revised";
  if (st === "drafted" || st === "drafting") return "drafted";
  if (st === "complete") return "approved";
  return "none";
}
