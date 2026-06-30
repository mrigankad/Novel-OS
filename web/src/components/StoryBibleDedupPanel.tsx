import { useCallback, useEffect, useRef, useState } from "react";
import { api, type BibleDuplicateGroup } from "../api/client";
import Modal, { fieldClass } from "./Modal";
import { useToast } from "./Toaster";
import { useBackgroundJob } from "../hooks/useBackgroundJob";

const SECTION_LABELS: Record<string, string> = {
  themes: "Themes",
  setting_summary: "Setting",
  historical_context: "Historical context",
  premise_beats: "Premise beats",
  import_notes: "Story notes",
  world_rules: "World rules",
};

function groupKey(g: BibleDuplicateGroup): string {
  return g.members.map((m) => m.id).sort().join("|");
}

export default function StoryBibleDedupPanel({
  projectId,
  open,
  onClose,
  onDone,
  onStatusChange,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
  onStatusChange?: () => void;
}) {
  const toast = useToast();
  const { watchBackgroundJob, isProjectJobRunning } = useBackgroundJob();
  const listRef = useRef<HTMLDivElement>(null);
  const [groups, setGroups] = useState<BibleDuplicateGroup[]>([]);
  const [keep, setKeep] = useState<Record<string, string>>({});
  const [textOverrides, setTextOverrides] = useState<Record<string, string>>({});
  const [source, setSource] = useState<"heuristic" | "ai">("heuristic");
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  const [autoBusy, setAutoBusy] = useState(false);

  const scanning = isProjectJobRunning("bible-dedup", projectId);

  const applyReport = useCallback((r: Awaited<ReturnType<typeof api.bibleDuplicates>>) => {
    setGroups(r.groups);
    setSource(r.source === "ai" ? "ai" : "heuristic");
    const defaults: Record<string, string> = {};
    for (const g of r.groups) {
      const suggested = g.members.find(
        (m) => m.index === g.suggested_keep_index && m.section === g.section,
      );
      defaults[groupKey(g)] = suggested?.id ?? g.members[0]?.id ?? "";
    }
    setKeep(defaults);
    setTextOverrides({});
  }, []);

  const load = useCallback(async (preferAi: boolean, opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    const scrollTop = silent ? listRef.current?.scrollTop ?? 0 : 0;
    if (!silent) setLoading(true);
    try {
      const r = await api.bibleDuplicates(projectId, preferAi);
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

  const refreshFromDisk = useCallback(async () => {
    try {
      const status = await api.bibleDedupStatus(projectId);
      await load(status.ai_suggestions_ready, { silent: false });
      onStatusChange?.();
    } catch {
      await load(false, { silent: false });
    }
  }, [projectId, load, onStatusChange]);

  useEffect(() => {
    if (open) void refreshFromDisk();
  }, [open, refreshFromDisk]);

  function removeGroup(g: BibleDuplicateGroup) {
    const key = groupKey(g);
    setGroups((prev) => prev.filter((x) => groupKey(x) !== key));
    setKeep((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setTextOverrides((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  async function runAiScan() {
    try {
      const job = await api.aiScanBibleDuplicates(projectId);
      toast(
        "Story bible AI scan started — close this and keep editing; you'll get a toast when it's done.",
        "success",
      );
      watchBackgroundJob(job.job_id, {
        label: "Story bible AI scan",
        kind: "bible-dedup",
        projectId,
        successMessage: "Story bible AI scan complete — open Deduplicate bible to review",
        onSuccess: () => {
          if (open) void refreshFromDisk();
          onStatusChange?.();
        },
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function autoDedupe() {
    setAutoBusy(true);
    try {
      const r = await api.autoDedupeBible(projectId);
      toast(`Saved — removed ${r.removed} duplicate bible line(s)`, "success");
      onDone();
      await load(false);
      onStatusChange?.();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setAutoBusy(false);
    }
  }

  async function mergeGroup(g: BibleDuplicateGroup) {
    const key = groupKey(g);
    const keepId = keep[key] ?? g.members[0]?.id;
    const keepMember = g.members.find((m) => m.id === keepId) ?? g.members[0];
    if (!keepMember || g.members.length < 2) return;
    const scrollTop = listRef.current?.scrollTop ?? 0;
    setMerging(key);
    try {
      const result = await api.mergeBibleDuplicates(projectId, {
        keep_section: keepMember.section,
        keep_index: keepMember.index,
        members: g.members,
        text_override: textOverrides[key]?.trim() ?? "",
      });
      removeGroup(g);
      onDone();
      const preview = (result.keep_text || textOverrides[key]?.trim() || keepMember.label).slice(0, 72);
      toast(`Saved — merged into: ${preview}${preview.length >= 72 ? "…" : ""}`, "success");
      await load(source === "ai", { silent: true });
      onStatusChange?.();
      requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = scrollTop;
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setMerging(null);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Deduplicate story bible" size="wide">
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        Find and merge duplicate or near-duplicate lines across themes, setting, premise beats,
        and other bible lists. Merges save immediately. AI scans run in the background — close this
        dialog anytime and come back when you're ready.
      </p>

      {scanning && (
        <p className="mb-3 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2 text-[12.5px] text-ink-text">
          AI scan running in background — you can close this dialog and keep editing the bible.
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        <button type="button" onClick={() => load(false)} disabled={loading || scanning}
                className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
          Quick scan
        </button>
        <button type="button" onClick={runAiScan} disabled={loading || scanning}
                className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/15 disabled:opacity-40">
          {scanning ? "AI scanning…" : "AI scan (LM Studio)"}
        </button>
        <button type="button" onClick={autoDedupe} disabled={autoBusy || groups.length === 0}
                className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
          {autoBusy ? "Merging…" : "Auto-remove obvious duplicates"}
        </button>
      </div>

      {source === "ai" && (
        <p className="mb-3 text-[12px] font-medium text-amber-deep">Showing AI suggestions</p>
      )}

      {loading ? (
        <p className="py-8 text-center text-[13px] text-ink-muted">Scanning…</p>
      ) : groups.length === 0 ? (
        <p className="rounded-lg border border-dashed border-paper-line px-5 py-8 text-center text-[13.5px] text-ink-muted">
          No duplicate bible lines found. Try AI scan if quick match missed rephrased entries.
        </p>
      ) : (
        <div ref={listRef} className="flex max-h-[55vh] flex-col gap-3 overflow-y-auto pr-1">
          {groups.map((g) => {
            const key = groupKey(g);
            const keepId = keep[key] ?? g.members[0]?.id;
            const keepMember = g.members.find((m) => m.id === keepId) ?? g.members[0];
            return (
              <div key={key} className="rounded-xl border border-paper-line bg-paper-card p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[13px] text-ink-muted">
                    {g.reason}
                    <span className="ml-2 text-[11px] text-amber-deep">
                      {Math.round(g.confidence * 100)}% match
                    </span>
                  </p>
                  <button type="button" onClick={() => mergeGroup(g)} disabled={merging === key}
                          className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-[12px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
                    {merging === key ? "Saving…" : "Merge & save"}
                  </button>
                </div>
                <ul className="mb-3 flex flex-col gap-1.5">
                  {g.members.map((m) => (
                    <li key={m.id}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 hover:bg-ink/5">
                        <input
                          type="radio"
                          name={`keep-${key}`}
                          className="mt-1"
                          checked={keepId === m.id}
                          onChange={() => setKeep((prev) => ({ ...prev, [key]: m.id }))}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                            {SECTION_LABELS[m.section] ?? m.section}
                          </span>
                          <span className="text-[13px] text-ink-text">{m.label}</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
                <label className="block text-[11px] font-medium text-ink-muted">
                  Canonical text override
                  <textarea
                    className={`${fieldClass} mt-1 min-h-[56px] w-full text-[13px] leading-snug`}
                    rows={2}
                    value={textOverrides[key] ?? ""}
                    placeholder={keepMember?.label ?? "Your merged wording — replaces the kept line"}
                    onChange={(e) => setTextOverrides((prev) => ({ ...prev, [key]: e.target.value }))}
                    disabled={merging === key}
                  />
                </label>
                <p className="mt-1 text-[10px] text-ink-muted">
                  Leave blank to keep the selected line; other duplicates are removed.
                </p>
              </div>
            );
          })}
        </div>
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
