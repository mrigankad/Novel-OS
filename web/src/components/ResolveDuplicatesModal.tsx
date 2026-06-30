import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DuplicateGroupModel } from "../api/client";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import ManualMergeModal, { type MergeKind } from "./ManualMergeModal";
import Modal, { fieldClass } from "./Modal";
import { useToast } from "./Toaster";

function groupKey(g: DuplicateGroupModel): string {
  return `${g.kind}:${g.members.map((m) => m.id).sort().join(",")}`;
}

export default function ResolveDuplicatesModal({
  projectId, open, onClose, onDone, defaultKind = "character", onStatusChange,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
  defaultKind?: MergeKind;
  onStatusChange?: () => void;
}) {
  const toast = useToast();
  const { watchBackgroundJob, isProjectJobRunning } = useBackgroundJob();
  const listRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<"suggested" | "manual">("suggested");
  const [manualKind, setManualKind] = useState<MergeKind>(defaultKind);
  const [source, setSource] = useState<"heuristic" | "ai">("heuristic");
  const [aiScanCompleted, setAiScanCompleted] = useState(false);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [characters, setCharacters] = useState<DuplicateGroupModel[]>([]);
  const [plotThreads, setPlotThreads] = useState<DuplicateGroupModel[]>([]);
  const [keepIds, setKeepIds] = useState<Record<string, string>>({});
  const [labelOverrides, setLabelOverrides] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  const [autoBusy, setAutoBusy] = useState(false);

  const scanning = isProjectJobRunning("entity-dedup", projectId);

  const applyReport = useCallback((r: Awaited<ReturnType<typeof api.duplicates>>) => {
    setCharacters(r.characters);
    setPlotThreads(r.plot_threads);
    setSource(r.source === "ai" ? "ai" : "heuristic");
    setAiScanCompleted(Boolean(r.ai_scan_completed));
    setScannedAt(r.scanned_at ?? null);
    const defaults: Record<string, string> = {};
    for (const g of [...r.characters, ...r.plot_threads]) {
      defaults[groupKey(g)] = g.suggested_keep_id;
    }
    setKeepIds(defaults);
    setLabelOverrides({});
  }, []);

  const load = useCallback(async (preferAi: boolean, opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    const scrollTop = silent ? listRef.current?.scrollTop ?? 0 : 0;
    if (!silent) setLoading(true);
    try {
      const r = await api.duplicates(projectId, preferAi);
      applyReport(r);
      if (silent) {
        requestAnimationFrame(() => {
          if (listRef.current) listRef.current.scrollTop = scrollTop;
        });
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [projectId, toast, applyReport]);

  const refreshFromDisk = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? true;
    try {
      const status = await api.duplicatesStatus(projectId);
      const preferAi = Boolean(status.has_ai_file || status.ai_suggestions_ready);
      await load(preferAi, { silent });
      onStatusChange?.();
    } catch {
      await load(false, { silent });
    }
  }, [projectId, load, onStatusChange]);

  useEffect(() => {
    if (open) {
      setView("suggested");
      setManualKind(defaultKind);
      void refreshFromDisk({ silent: false });
    }
  }, [open, defaultKind, refreshFromDisk]);

  function removeGroup(g: DuplicateGroupModel) {
    const key = groupKey(g);
    if (g.kind === "character") {
      setCharacters((prev) => prev.filter((x) => groupKey(x) !== key));
    } else {
      setPlotThreads((prev) => prev.filter((x) => groupKey(x) !== key));
    }
    setKeepIds((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setLabelOverrides((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  async function runAiScan() {
    try {
      const job = await api.aiScanDuplicates(projectId);
      toast(
        "Duplicate scan started — close this dialog and keep working; you'll get a toast when it's done.",
        "success",
      );
      watchBackgroundJob(job.job_id, {
        label: "Duplicate scan",
        kind: "entity-dedup",
        projectId,
        successMessage: "Duplicate AI scan complete — reopen Resolve duplicates to review",
        onSuccess: () => {
          void refreshFromDisk({ silent: true });
          onStatusChange?.();
        },
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function autoMerge() {
    setAutoBusy(true);
    try {
      const r = await api.autoResolveDuplicates(projectId);
      toast(
        `Auto-merged ${r.merged_characters} characters, ${r.merged_plot_threads} plot threads — saved`,
        "success",
      );
      onDone();
      await load(false);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setAutoBusy(false);
    }
  }

  async function mergeGroup(g: DuplicateGroupModel) {
    const key = groupKey(g);
    const keep = keepIds[key] ?? g.suggested_keep_id;
    const mergeIds = g.members.map((m) => m.id).filter((id) => id !== keep);
    if (mergeIds.length === 0) return;
    const scrollTop = listRef.current?.scrollTop ?? 0;
    setMerging(key);
    try {
      const result = await api.mergeDuplicates(projectId, {
        kind: g.kind,
        keep_id: keep,
        merge_ids: mergeIds,
        label_override: labelOverrides[key]?.trim() ?? "",
      });
      removeGroup(g);
      onDone();
      const label = result.keep_label || labelOverrides[key]?.trim() || "entry";
      toast(`Saved — merged into "${label}"`, "success");
      await load(source === "ai", { silent: true });
      requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = scrollTop;
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setMerging(null);
    }
  }

  const totalGroups = characters.length + plotThreads.length;
  const plotFocus = defaultKind === "plot_thread";
  const plotGroupsForFocus = plotThreads.length;
  const charGroupsForFocus = characters.length;

  function emptyStateMessage(): string {
    if (source === "ai" && aiScanCompleted && totalGroups === 0) {
      if (plotFocus) {
        return "AI scan completed — no duplicate plot threads found. Character duplicates may still appear if the model found any.";
      }
      return "AI scan completed — no duplicate characters or plot threads found.";
    }
    if (source === "ai" && totalGroups === 0) {
      return "Saved AI suggestions are empty or were already merged. Run AI scan again if you still suspect duplicates.";
    }
    return "No duplicate groups found with the current scan.";
  }

  if (view === "manual") {
    return (
      <ManualMergeModal
        projectId={projectId}
        kind={manualKind}
        open={open}
        onClose={onClose}
        onCancel={() => setView("suggested")}
        cancelLabel="Back"
        onDone={() => {
          onDone();
          setView("suggested");
          load(source === "ai");
        }}
      />
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="Resolve duplicate entries" size="wide">
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        Merge characters and plot threads that refer to the same person or storyline.
        Quick match uses name similarity; AI scan uses LM Studio for ambiguous cases.
        AI scans run in the background like chapter revision — close this dialog anytime.
        Merges save immediately. Optional canonical name replaces all entries in the group.
        If the scanner misses a pair, use{" "}
        <button type="button" onClick={() => setView("manual")}
                className="font-semibold text-amber-deep underline-offset-2 hover:underline">
          manual merge
        </button>.
      </p>

      {scanning && (
        <p className="mb-3 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2 text-[12.5px] text-ink-text">
          AI scan running in background — close this dialog and keep working elsewhere.
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => { setManualKind("character"); setView("manual"); }}
                className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5">
          Merge characters manually…
        </button>
        <button type="button" onClick={() => { setManualKind("plot_thread"); setView("manual"); }}
                className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5">
          Merge plot threads manually…
        </button>
        <button type="button" onClick={() => load(false)} disabled={loading || scanning}
                className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
          Quick scan
        </button>
        <button type="button" onClick={runAiScan} disabled={loading || scanning}
                className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/15 disabled:opacity-40">
          {scanning ? "AI scanning…" : "AI scan (LM Studio)"}
        </button>
        <button type="button" onClick={autoMerge} disabled={autoBusy || totalGroups === 0}
                className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
          {autoBusy ? "Merging…" : "Auto-merge obvious duplicates"}
        </button>
      </div>

      {source === "ai" && (
        <p className="mb-3 text-[12px] font-medium text-amber-deep">
          Showing AI suggestions
          {scannedAt ? ` · scanned ${new Date(scannedAt).toLocaleString()}` : ""}
        </p>
      )}

      {loading ? (
        <p className="py-8 text-center text-[13px] text-ink-muted">Scanning…</p>
      ) : totalGroups === 0 ? (
        <div className="rounded-lg border border-dashed border-paper-line px-5 py-8 text-center">
          <p className="text-[13.5px] text-ink-muted">
            {emptyStateMessage()}
          </p>
          <button type="button" onClick={() => { setManualKind(plotFocus ? "plot_thread" : "character"); setView("manual"); }}
                  className="mt-3 rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800">
            {plotFocus ? "Pick plot threads to merge manually" : "Pick characters to merge manually"}
          </button>
        </div>
      ) : (
        <>
          {plotFocus && plotGroupsForFocus === 0 && charGroupsForFocus > 0 && (
            <div className="mb-4 rounded-lg border border-dashed border-paper-line px-5 py-4 text-center">
              <p className="text-[13.5px] text-ink-muted">
                No duplicate plot threads in this scan. Character groups are listed below.
              </p>
            </div>
          )}
          <div
            ref={listRef}
            className="flex max-h-[55vh] flex-col gap-6 overflow-y-auto pr-1"
          >
            {characters.length > 0 && (
              <DuplicateSection
                title="Characters"
                groups={characters}
                keepIds={keepIds}
                labelOverrides={labelOverrides}
                merging={merging}
                onKeepChange={(k, id) => setKeepIds((prev) => ({ ...prev, [k]: id }))}
                onLabelOverrideChange={(k, text) => setLabelOverrides((prev) => ({ ...prev, [k]: text }))}
                onMerge={mergeGroup}
              />
            )}
            {plotThreads.length > 0 && (
              <DuplicateSection
                title="Plot threads"
                groups={plotThreads}
                keepIds={keepIds}
                labelOverrides={labelOverrides}
                merging={merging}
                onKeepChange={(k, id) => setKeepIds((prev) => ({ ...prev, [k]: id }))}
                onLabelOverrideChange={(k, text) => setLabelOverrides((prev) => ({ ...prev, [k]: text }))}
                onMerge={mergeGroup}
              />
            )}
          </div>
        </>
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

function DuplicateSection({
  title, groups, keepIds, labelOverrides, merging, onKeepChange, onLabelOverrideChange, onMerge,
}: {
  title: string;
  groups: DuplicateGroupModel[];
  keepIds: Record<string, string>;
  labelOverrides: Record<string, string>;
  merging: string | null;
  onKeepChange: (key: string, id: string) => void;
  onLabelOverrideChange: (key: string, text: string) => void;
  onMerge: (g: DuplicateGroupModel) => void;
}) {
  const isCharacter = groups[0]?.kind === "character";
  return (
    <section>
      <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wider text-ink-muted">{title}</h3>
      <div className="flex flex-col gap-3">
        {groups.map((g) => {
          const key = groupKey(g);
          const keep = keepIds[key] ?? g.suggested_keep_id;
          const keepMember = g.members.find((m) => m.id === keep);
          return (
            <div key={key} className="rounded-xl border border-paper-line bg-paper-card p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[13px] text-ink-muted">
                  {g.reason}
                  <span className="ml-2 text-[11px] text-amber-deep">
                    {Math.round(g.confidence * 100)}% match
                  </span>
                </p>
                <button type="button" onClick={() => onMerge(g)} disabled={merging === key}
                        className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-[12px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
                  {merging === key ? "Saving…" : "Merge & save"}
                </button>
              </div>
              <ul className="mb-3 flex flex-col gap-1.5">
                {g.members.map((m) => (
                  <li key={m.id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-ink/5">
                      <input
                        type="radio"
                        name={`keep-${key}`}
                        checked={keep === m.id}
                        onChange={() => onKeepChange(key, m.id)}
                      />
                      <span className="text-[13.5px] font-medium text-ink-text">{m.label}</span>
                      {m.role && (
                        <span className="text-[11px] capitalize text-ink-muted">{m.role}</span>
                      )}
                      {m.thread_type && (
                        <span className="text-[11px] text-ink-muted">{m.thread_type}</span>
                      )}
                      {m.id === g.suggested_keep_id && (
                        <span className="text-[10px] font-semibold uppercase text-amber-deep">suggested</span>
                      )}
                    </label>
                  </li>
                ))}
              </ul>
              <label className="block text-[11px] font-medium text-ink-muted">
                {isCharacter ? "Canonical name override" : "Canonical plot name override"}
                <input
                  type="text"
                  className={`${fieldClass} mt-1 w-full text-[13px]`}
                  value={labelOverrides[key] ?? ""}
                  placeholder={keepMember?.label ?? "Leave blank to keep longest name"}
                  onChange={(e) => onLabelOverrideChange(key, e.target.value)}
                  disabled={merging === key}
                />
              </label>
              <p className="mt-1 text-[10px] text-ink-muted">
                Other names become aliases (characters) or are removed (plots).
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
