import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../components/Toaster";

export type BackgroundJobKind =
  | "bible-dedup"
  | "entity-dedup"
  | "mine-plots"
  | "mine-characters"
  | "mine-bible";

type Watcher = {
  timer: number;
  label: string;
  kind: BackgroundJobKind;
  projectId: string;
  scope?: string;
  onSuccess?: () => void;
};

const watchers = new Map<string, Watcher>();
const byProjectKind = new Map<string, string>();
const listeners = new Set<() => void>();

let toastSuccess: ((msg: string) => void) | null = null;
let toastError: ((msg: string) => void) | null = null;

function jobKey(kind: BackgroundJobKind, projectId: string, scope?: string): string {
  return scope ? `${kind}:${projectId}:${scope}` : `${kind}:${projectId}`;
}

function notify() {
  listeners.forEach((fn) => fn());
}

function stopWatcher(jobId: string) {
  const w = watchers.get(jobId);
  if (!w) return;
  window.clearInterval(w.timer);
  watchers.delete(jobId);
  const pk = jobKey(w.kind, w.projectId, w.scope);
  if (byProjectKind.get(pk) === jobId) byProjectKind.delete(pk);
  notify();
}

export function watchBackgroundJob(
  jobId: string,
  opts: {
    label: string;
    kind: BackgroundJobKind;
    projectId: string;
    scope?: string;
    onSuccess?: () => void;
    successMessage?: string;
  },
) {
  const pk = jobKey(opts.kind, opts.projectId, opts.scope);
  const existing = byProjectKind.get(pk);
  if (existing && existing !== jobId) stopWatcher(existing);

  byProjectKind.set(pk, jobId);
  notify();

  const timer = window.setInterval(async () => {
    try {
      const s = await api.getJob(jobId);
      if (s.status === "running") return;
      stopWatcher(jobId);
      if (s.status === "done") {
        toastSuccess?.(opts.successMessage ?? `${opts.label} complete — reopen to review results`);
        opts.onSuccess?.();
      } else {
        toastError?.(s.error ?? `${opts.label} failed`);
      }
    } catch (e) {
      stopWatcher(jobId);
      toastError?.(e instanceof Error ? e.message : String(e));
    }
  }, 1500);

  watchers.set(jobId, {
    timer,
    label: opts.label,
    kind: opts.kind,
    projectId: opts.projectId,
    scope: opts.scope,
    onSuccess: opts.onSuccess,
  });
}

export function isProjectJobRunning(
  kind: BackgroundJobKind,
  projectId: string,
  scope?: string,
): boolean {
  const jobId = byProjectKind.get(jobKey(kind, projectId, scope));
  return jobId != null && watchers.has(jobId);
}

/** Poll job state across the app (survives modal close / tab switches). */
export function useBackgroundJob() {
  const toast = useToast();
  const [, tick] = useState(0);

  useEffect(() => {
    toastSuccess = (msg) => toast(msg, "success");
    toastError = (msg) => toast(msg, "error");
    const bump = () => tick((n) => n + 1);
    listeners.add(bump);
    return () => {
      listeners.delete(bump);
    };
  }, [toast]);

  return { watchBackgroundJob, isProjectJobRunning };
}
