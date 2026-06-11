import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../components/Toaster";

const LABELS: Record<string, string> = {
  plan_outline: "Planning outline",
  plan_chapter: "Planning chapter",
  write: "Drafting",
  edit: "Revising",
  validate: "Validating",
  approve: "Approving",
};

/**
 * Runs a pipeline stage as a background job and polls until it finishes.
 * `runningStage` reflects which stage is in flight (for per-button spinners).
 */
export function useRunPhase(projectId: string, onDone?: () => void) {
  const toast = useToast();
  const [runningStage, setRunningStage] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current);
    },
    [],
  );

  async function run(stage: string, params: Record<string, unknown> = {}) {
    if (runningStage) return;
    setRunningStage(stage);
    try {
      const job = await api.runPhase(projectId, stage, params);
      timer.current = window.setInterval(async () => {
        try {
          const s = await api.getJob(job.job_id);
          if (s.status === "running") return;
          if (timer.current) window.clearInterval(timer.current);
          setRunningStage(null);
          if (s.status === "done") {
            toast(`${LABELS[stage] ?? stage} complete`, "success");
            onDone?.();
          } else {
            toast(s.error ?? "Agent run failed", "error");
          }
        } catch (e) {
          if (timer.current) window.clearInterval(timer.current);
          setRunningStage(null);
          toast(e instanceof Error ? e.message : String(e), "error");
        }
      }, 1200);
    } catch (e) {
      setRunningStage(null);
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  return { run, runningStage, isRunning: runningStage != null, label: LABELS };
}
