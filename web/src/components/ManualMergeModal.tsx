import { useEffect, useMemo, useState } from "react";
import { api, type CharacterSummary, type PlotThreadSummary } from "../api/client";
import Modal, { fieldClass } from "./Modal";
import { useToast } from "./Toaster";

export type MergeKind = "character" | "plot_thread";

const EMPTY_SELECTED: string[] = [];

const ROLE_RANK: Record<string, number> = {
  protagonist: 4,
  antagonist: 3,
  supporting: 2,
  minor: 1,
};

function suggestKeepId(
  kind: MergeKind,
  items: Array<{ id: string; label: string; role?: string }>,
  selectedIds: string[],
): string {
  const selected = items.filter((i) => selectedIds.includes(i.id));
  if (selected.length === 0) return "";
  if (kind === "character") {
    return [...selected].sort((a, b) => {
      const ra = ROLE_RANK[a.role ?? "minor"] ?? 0;
      const rb = ROLE_RANK[b.role ?? "minor"] ?? 0;
      if (rb !== ra) return rb - ra;
      return b.label.length - a.label.length;
    })[0].id;
  }
  return [...selected].sort((a, b) => b.label.length - a.label.length)[0].id;
}

export default function ManualMergeModal({
  projectId,
  kind,
  open,
  onClose,
  onDone,
  initialSelected = EMPTY_SELECTED,
  onCancel,
  cancelLabel = "Cancel",
  defaultPlotMode = "parallel",
}: {
  projectId: string;
  kind: MergeKind;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
  initialSelected?: string[];
  onCancel?: () => void;
  cancelLabel?: string;
  defaultPlotMode?: "parallel" | "nest";
}) {
  const toast = useToast();
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [plotThreads, setPlotThreads] = useState<PlotThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [keepOverride, setKeepOverride] = useState<string | null>(null);
  const [plotMergeMode, setPlotMergeMode] = useState<"parallel" | "nest">("parallel");
  const [labelOverride, setLabelOverride] = useState("");
  const [merging, setMerging] = useState(false);

  const initialSelectedKey = initialSelected.join("\0");

  useEffect(() => {
    if (!open) return;
    setSelectedIds([...initialSelected]);
    setKeepOverride(null);
    setLabelOverride("");
    setPlotMergeMode(defaultPlotMode);
    setLoadError(null);
    let alive = true;
    setLoading(true);
    const req = kind === "character"
      ? api.characters(projectId)
      : api.plotThreads(projectId);
    req
      .then((rows) => {
        if (!alive) return;
        if (kind === "character") setCharacters(rows as CharacterSummary[]);
        else setPlotThreads(rows as PlotThreadSummary[]);
      })
      .catch((err) => {
        if (!alive) return;
        const msg = err instanceof Error ? err.message : String(err);
        setLoadError(msg);
        toast(msg, "error");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => { alive = false; };
  }, [open, kind, projectId, initialSelectedKey, defaultPlotMode, toast]);

  const items = useMemo(() => {
    if (kind === "character") {
      return characters.map((c) => ({
        id: c.id,
        label: c.full_name,
        role: c.role,
        hint: c.aliases?.length ? `aka ${c.aliases.join(", ")}` : undefined,
      }));
    }
    return plotThreads.map((t) => ({
      id: t.id,
      label: t.name,
      role: t.thread_type,
      hint: t.description ? t.description.slice(0, 80) : undefined,
    }));
  }, [kind, characters, plotThreads]);

  const keepId = useMemo(() => {
    if (selectedIds.length < 2) return "";
    const suggested = suggestKeepId(kind, items, selectedIds);
    if (keepOverride && selectedIds.includes(keepOverride)) return keepOverride;
    return suggested;
  }, [selectedIds, items, kind, keepOverride]);

  function toggle(id: string) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      return [...prev, id];
    });
    setKeepOverride(null);
  }

  async function merge() {
    if (selectedIds.length < 2 || !keepId) return;
    const mergeIds = selectedIds.filter((id) => id !== keepId);
    setMerging(true);
    try {
      await api.mergeDuplicates(projectId, {
        kind: kind === "character" ? "character" : "plot_thread",
        keep_id: keepId,
        merge_ids: mergeIds,
        mode: kind === "plot_thread" ? plotMergeMode : "parallel",
        label_override: labelOverride.trim(),
      });
      const keepLabel = labelOverride.trim() || items.find((i) => i.id === keepId)?.label || "entry";
      if (kind === "character") {
        toast(
          `Merged ${mergeIds.length} character(s) into ${keepLabel}. Other names saved as aliases.`,
          "success",
        );
      } else if (plotMergeMode === "nest") {
        toast(
          `Nested ${mergeIds.length} plot thread(s) under ${keepLabel} as subplots.`,
          "success",
        );
      } else {
        toast(
          `Merged ${mergeIds.length} plot thread(s) into ${keepLabel}.`,
          "success",
        );
      }
      onDone();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setMerging(false);
    }
  }

  const title = kind === "character"
    ? "Merge characters manually"
    : plotMergeMode === "nest"
      ? "Nest plots as subplots"
      : "Merge plot threads manually";
  const noun = kind === "character" ? "character" : "plot thread";

  const handleDismiss = onCancel ?? onClose;

  return (
    <Modal open={open} onClose={handleDismiss} title={title}>
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        {kind === "character" ? (
          <>
            Select two or more {noun}s that refer to the same person. Pick which entry to keep — the others
            are removed and their names become aliases on the kept character.
          </>
        ) : plotMergeMode === "nest" ? (
          <>
            Select a <strong>parent</strong> plot thread and one or more threads to fold in as{" "}
            <strong>subplot lines</strong> (one line per nested thread). Nested threads are removed from the list.
          </>
        ) : (
          <>
            Select duplicate {noun}s that refer to the same storyline. Pick which entry to keep — the others
            are merged into it (parallel merge).
          </>
        )}
      </p>

      {kind === "plot_thread" && (
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            onClick={() => setPlotMergeMode("parallel")}
            className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${
              plotMergeMode === "parallel"
                ? "bg-ink text-on-ink"
                : "border border-paper-line text-ink-muted hover:bg-ink/5"
            }`}
          >
            Parallel merge
          </button>
          <button
            type="button"
            onClick={() => setPlotMergeMode("nest")}
            className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold ${
              plotMergeMode === "nest"
                ? "bg-ink text-on-ink"
                : "border border-paper-line text-ink-muted hover:bg-ink/5"
            }`}
          >
            Nest as subplots
          </button>
        </div>
      )}

      {loading ? (
        <p className="py-8 text-center text-[13px] text-ink-muted">Loading…</p>
      ) : loadError ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-5 py-8 text-center text-[13.5px] text-red-700">
          Could not load {noun}s: {loadError}
        </p>
      ) : items.length < 2 ? (
        <p className="rounded-lg border border-dashed border-paper-line px-5 py-8 text-center text-[13.5px] text-ink-muted">
          Need at least two {noun}s to merge.
        </p>
      ) : (
        <>
          <div className="mb-4 flex max-h-[40vh] flex-col gap-1 overflow-y-auto rounded-xl border border-paper-line bg-paper-card p-2">
            {items.map((item) => (
              <label
                key={item.id}
                className={`flex cursor-pointer items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-ink/5 ${
                  selectedIds.includes(item.id) ? "bg-amber/5 ring-1 ring-amber/30" : ""
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selectedIds.includes(item.id)}
                  onChange={() => toggle(item.id)}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-ink-text">{item.label}</p>
                  <p className="text-[11px] capitalize text-ink-muted">{item.role}</p>
                  {item.hint && (
                    <p className="mt-0.5 truncate text-[11px] text-ink-muted/80">{item.hint}</p>
                  )}
                </div>
              </label>
            ))}
          </div>

          {selectedIds.length >= 2 && (
            <div className="mb-4 rounded-xl border border-paper-line bg-paper-card p-4">
              <p className="mb-2 text-[12px] font-bold uppercase tracking-wider text-ink-muted">
                {kind === "plot_thread" && plotMergeMode === "nest" ? "Parent thread" : "Keep as primary"}
              </p>
              <ul className="flex flex-col gap-1">
                {items
                  .filter((i) => selectedIds.includes(i.id))
                  .map((item) => (
                    <li key={item.id}>
                      <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-ink/5">
                        <input
                          type="radio"
                          name="manual-merge-keep"
                          checked={keepId === item.id}
                          onChange={() => setKeepOverride(item.id)}
                        />
                        <span className="text-[13.5px] font-medium text-ink-text">{item.label}</span>
                        {item.id === suggestKeepId(kind, items, selectedIds) && (
                          <span className="text-[10px] font-semibold uppercase text-amber-deep">
                            suggested
                          </span>
                        )}
                      </label>
                    </li>
                  ))}
              </ul>
              <p className="mt-2 text-[12px] text-ink-muted">
                {plotMergeMode === "nest"
                  ? `${selectedIds.length - 1} other thread(s) will become subplot lines under this parent.`
                  : `${selectedIds.length - 1} other ${selectedIds.length === 2 ? "entry" : "entries"} will merge into this one.`}
              </p>
              <label className="mt-3 block text-[11px] font-medium text-ink-muted">
                {kind === "character" ? "Canonical name override" : "Canonical plot name override"}
                <input
                  type="text"
                  className={`${fieldClass} mt-1 w-full text-[13px]`}
                  value={labelOverride}
                  onChange={(e) => setLabelOverride(e.target.value)}
                  placeholder="Optional — replaces all merged names"
                  disabled={merging}
                />
              </label>
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={handleDismiss}
              disabled={merging}
              className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={merge}
              disabled={merging || selectedIds.length < 2 || !keepId}
              className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {merging ? "Working…" : plotMergeMode === "nest" ? "Nest selected" : `Merge ${selectedIds.length >= 2 ? selectedIds.length : ""} selected`.trim()}
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
