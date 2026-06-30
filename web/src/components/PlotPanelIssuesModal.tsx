import { useCallback, useEffect, useState } from "react";
import { api, type PlotPanelIssue } from "../api/client";
import Modal from "./Modal";
import { useToast } from "./Toaster";

const KIND_LABELS: Record<string, string> = {
  duplicate_subplot_within: "Duplicate on same plot",
  duplicate_subplot_across: "Same subplot on multiple plots",
  thread_under_wrong_parent: "Thread matches subplot elsewhere",
  subplot_matches_thread: "Subplot matches separate thread",
};

export default function PlotPanelIssuesModal({
  projectId, open, onClose, onDone,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [issues, setIssues] = useState<PlotPanelIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  const [autoBusy, setAutoBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.plotPanelIssues(projectId);
      setIssues(r.issues);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setLoading(false);
    }
  }, [projectId, toast]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  async function resolveOne(issue: PlotPanelIssue) {
    setResolving(issue.issue_id);
    try {
      const r = await api.resolvePlotPanelIssue(projectId, issue.issue_id);
      toast(r.log[0] ?? "Issue resolved", "success");
      onDone();
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setResolving(null);
    }
  }

  async function autoResolve() {
    setAutoBusy(true);
    try {
      const r = await api.autoResolvePlotPanelIssues(projectId);
      toast(`Resolved ${r.resolved} subplot issue(s)`, "success");
      onDone();
      await load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setAutoBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Plot & subplot issues" size="wide">
      <p className="mb-4 text-[13px] leading-relaxed text-ink-muted">
        Scans duplicate subplot lines and plot threads that belong under a different parent.
        Story bible entries are not included — only plot-thread fields on this page.
      </p>

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading || autoBusy}
          onClick={() => load()}
          className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-50"
        >
          {loading ? "Scanning…" : "Rescan"}
        </button>
        <button
          type="button"
          disabled={loading || autoBusy || issues.length === 0}
          onClick={() => void autoResolve()}
          className="rounded-lg border border-amber/40 bg-amber/5 px-3 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-amber/10 disabled:opacity-50"
        >
          {autoBusy ? "Fixing…" : "Auto-fix high confidence"}
        </button>
      </div>

      {loading && issues.length === 0 ? (
        <p className="text-[13px] text-ink-muted">Scanning plot threads…</p>
      ) : issues.length === 0 ? (
        <p className="rounded-lg border border-dashed border-paper-line bg-paper-card/60 px-4 py-6 text-center text-[13px] text-ink-muted">
          No cross-field plot or subplot issues found.
        </p>
      ) : (
        <ul className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
          {issues.map((issue) => (
            <li
              key={issue.issue_id}
              className="rounded-xl border border-paper-line bg-paper-card p-3"
            >
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="rounded bg-ink/5 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                  {KIND_LABELS[issue.kind] ?? issue.kind}
                </span>
                <span className="text-[11px] text-ink-muted">
                  {Math.round(issue.confidence * 100)}% match
                </span>
              </div>
              <p className="text-[13px] font-medium text-ink-text">{issue.reason}</p>
              {issue.subplot_line && (
                <p className="mt-1 font-mono text-[11px] text-ink-muted">{issue.subplot_line}</p>
              )}
              {issue.locations.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-[11px] text-ink-muted">
                  {issue.locations.map((loc) => (
                    <li key={`${loc.parent_id}-${loc.index}`}>
                      {loc.parent_name}: {loc.line.slice(0, 80)}
                      {loc.line.length > 80 ? "…" : ""}
                    </li>
                  ))}
                </ul>
              )}
              {issue.suggested_parent_name && (
                <p className="mt-1 text-[11px] text-ink-muted">
                  Suggested: {(issue.suggested_action ?? "fix").replace(/_/g, " ")} →{" "}
                  <span className="font-medium text-ink-text">{issue.suggested_parent_name}</span>
                </p>
              )}
              <button
                type="button"
                disabled={resolving === issue.issue_id}
                onClick={() => void resolveOne(issue)}
                className="mt-2 rounded-lg border border-paper-line px-3 py-1 text-[12px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-50"
              >
                {resolving === issue.issue_id ? "Fixing…" : "Fix this"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex justify-end">
        <button type="button" onClick={onClose}
                className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5">
          Close
        </button>
      </div>
    </Modal>
  );
}
