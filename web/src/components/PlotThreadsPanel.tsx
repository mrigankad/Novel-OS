import { useCallback, useEffect, useRef, useState } from "react";
import { api, type PlotThreadSummary } from "../api/client";
import DeleteButton from "./DeleteButton";
import EditorSaveBar, { formatSavedAt } from "./EditorSaveBar";
import { fieldClass } from "./Modal";
import { useToast } from "./Toaster";

async function pollJob(jobId: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const timer = window.setInterval(async () => {
      try {
        const s = await api.getJob(jobId);
        if (s.status === "running") return;
        window.clearInterval(timer);
        if (s.status === "done") resolve();
        else reject(new Error(s.error ?? "Job failed"));
      } catch (e) {
        window.clearInterval(timer);
        reject(e);
      }
    }, 1500);
  });
}

const THREAD_TYPES = ["main", "subplot", "character_arc", "mystery"];
const STATUSES = ["active", "resolved", "abandoned", "foreshadowed"];

type DraftRow = {
  name: string;
  description: string;
  subplotsText: string;
  thread_type: string;
  status: string;
  priority: number;
};

type DragMode = "reorder" | "nest" | null;

function rowFromThread(t: PlotThreadSummary): DraftRow {
  return {
    name: t.name,
    description: t.description,
    subplotsText: (t.subplots ?? []).join("\n"),
    thread_type: t.thread_type,
    status: t.status,
    priority: t.priority,
  };
}

function subplotsFromText(text: string): string[] {
  return text.split("\n").map((s) => s.trim()).filter(Boolean);
}

function subplotPreview(t: PlotThreadSummary): string {
  const subs = t.subplots ?? [];
  if (!subs.length) return "";
  if (subs.length === 1) return subs[0].length > 48 ? `${subs[0].slice(0, 45)}…` : subs[0];
  return `${subs.length} subplots`;
}

export default function PlotThreadsPanel({
  projectId,
  threads,
  onChange,
  onAdd,
}: {
  projectId: string;
  threads: PlotThreadSummary[];
  onChange: () => void;
  onAdd: () => void;
}) {
  const toast = useToast();
  const [order, setOrder] = useState<PlotThreadSummary[]>(threads);
  const [drafts, setDrafts] = useState<Record<string, DraftRow>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragMode, setDragMode] = useState<DragMode>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [plotDirty, setPlotDirty] = useState(false);
  const [plotLastSaved, setPlotLastSaved] = useState<string | null>(null);
  const [genPrompts, setGenPrompts] = useState<Record<string, string>>({});
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [bibleSuggestions, setBibleSuggestions] = useState<Record<string, string[]>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const orderRef = useRef(order);
  orderRef.current = order;

  useEffect(() => {
    setOrder(threads);
    setDrafts((prev) => {
      const next: Record<string, DraftRow> = {};
      for (const t of threads) {
        next[t.id] = prev[t.id] ?? rowFromThread(t);
      }
      return next;
    });
  }, [threads]);

  const flashSaved = useCallback(() => {
    setSaveState("saved");
    setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 1500);
  }, []);

  const persistReorder = useCallback(async (ids: string[]) => {
    setSaveState("saving");
    try {
      const updated = await api.reorderPlotThreads(projectId, ids);
      setOrder(updated);
      setPlotLastSaved(formatSavedAt());
      onChange();
      flashSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      onChange();
    } finally {
      setSaveState("idle");
    }
  }, [projectId, onChange, toast, flashSaved]);

  const persistThread = useCallback(async (threadId: string, draft: DraftRow) => {
    setSaveState("saving");
    try {
      const updated = await api.updatePlotThread(projectId, threadId, {
        name: draft.name.trim(),
        description: draft.description,
        thread_type: draft.thread_type,
        status: draft.status,
        priority: draft.priority,
        subplots: subplotsFromText(draft.subplotsText),
      });
      setOrder((list) => list.map((t) => (t.id === threadId ? updated : t)));
      setDrafts((d) => ({ ...d, [threadId]: rowFromThread(updated) }));
      setPlotDirty(false);
      setPlotLastSaved(formatSavedAt());
      onChange();
      flashSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setSaveState("idle");
    }
  }, [projectId, onChange, toast, flashSaved]);

  function queueSave(threadId: string, draft: DraftRow) {
    clearTimeout(timers.current[threadId]);
    timers.current[threadId] = setTimeout(() => {
      const orig = orderRef.current.find((t) => t.id === threadId);
      if (!orig) return;
      const changed =
        draft.name.trim() !== orig.name
        || draft.description !== orig.description
        || draft.thread_type !== orig.thread_type
        || draft.status !== orig.status
        || draft.priority !== orig.priority
        || subplotsFromText(draft.subplotsText).join("\n")
          !== (orig.subplots ?? []).join("\n");
      if (changed) void persistThread(threadId, draft);
    }, 700);
  }

  function patchDraft(threadId: string, patch: Partial<DraftRow>) {
    setPlotDirty(true);
    setDrafts((d) => {
      const next = { ...d[threadId], ...patch };
      queueSave(threadId, next);
      return { ...d, [threadId]: next };
    });
  }

  function clearDrag() {
    setDragId(null);
    setDragMode(null);
    setOverId(null);
  }

  function onReorderDragStart(id: string) {
    setDragId(id);
    setDragMode("reorder");
  }

  function onNestDragStart(id: string) {
    setDragId(id);
    setDragMode("nest");
  }

  function onDragOverRow(e: React.DragEvent, id: string) {
    e.preventDefault();
    if (!dragId || dragId === id) return;
    setOverId(id);
    if (dragMode === "nest") return;
  }

  async function onDropRow(targetId: string) {
    if (!dragId || dragId === targetId) {
      clearDrag();
      return;
    }

    if (dragMode === "nest") {
      try {
        setSaveState("saving");
        await api.nestPlotThreads(projectId, targetId, [dragId]);
        toast("Nested as subplot", "success");
        setPlotLastSaved(formatSavedAt());
        onChange();
        flashSaved();
      } catch (e) {
        toast(e instanceof Error ? e.message : String(e), "error");
      } finally {
        setSaveState("idle");
        clearDrag();
      }
      return;
    }

    const ids = order.map((t) => t.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) {
      clearDrag();
      return;
    }
    ids.splice(from, 1);
    ids.splice(to, 0, dragId);
    setOrder(ids.map((id) => order.find((t) => t.id === id)!));
    clearDrag();
    void persistReorder(ids);
  }

  async function deletePlot(t: PlotThreadSummary) {
    try {
      await api.deletePlotThread(projectId, t.id);
      toast(`Removed "${t.name}"`, "success");
      onChange();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  function toggleExpand(id: string) {
    setExpanded((e) => ({ ...e, [id]: !e[id] }));
  }

  async function generateDescription(threadId: string) {
    setGeneratingId(threadId);
    try {
      const job = await api.generatePlotThread(projectId, threadId, {
        prompt: genPrompts[threadId]?.trim() ?? "",
      });
      toast("Generating plot description…", "success");
      await pollJob(job.job_id);
      const preview = await api.getPlotGeneratePreview(projectId, threadId);
      if (!preview?.description) {
        throw new Error("No plot description was generated.");
      }
      patchDraft(threadId, { description: preview.description });
      if (preview.bible_suggestions?.length) {
        setBibleSuggestions((prev) => ({ ...prev, [threadId]: preview.bible_suggestions }));
      }
      await api.discardPlotGeneratePreview(projectId, threadId);
      toast("Description generated — review subplots & bible suggestions, then save", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <div>
      <EditorSaveBar
        dirty={plotDirty}
        saving={saveState === "saving"}
        lastSaved={plotLastSaved}
        autosaveOnly
        hint={
          <>
            <span className="font-medium text-ink-text">≡</span> reorder · drag{" "}
            <span className="font-medium text-ink-text">name</span> onto another to nest
          </>
        }
        autosaveNote
      />

      {order.length === 0 ? (
        <div className="rounded-lg border border-dashed border-paper-line bg-paper-card/60 px-6 py-8 text-center text-[13px] text-ink-muted">
          No plot threads yet.{" "}
          <button type="button" onClick={onAdd} className="font-semibold text-amber-deep hover:underline">
            + Add Plot Thread
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {order.map((t) => {
            const d = drafts[t.id] ?? rowFromThread(t);
            const isOpen = expanded[t.id] ?? false;
            const isOverNest = overId === t.id && dragMode === "nest" && dragId !== t.id;
            const isOverReorder = overId === t.id && dragMode === "reorder" && dragId !== t.id;
            const subCount = (t.subplots ?? []).length;
            const preview = subplotPreview(t);

            return (
              <div
                key={t.id}
                onDragOver={(e) => onDragOverRow(e, t.id)}
                onDrop={() => onDropRow(t.id)}
                className={`group relative rounded-lg border bg-paper-card transition-colors ${
                  isOverNest
                    ? "border-amber-deep bg-amber/10 ring-2 ring-amber/40"
                    : isOverReorder
                      ? "border-ink/30 bg-ink/[0.03]"
                      : "border-paper-line"
                } ${dragId === t.id ? "opacity-40" : ""}`}
              >
                {isOverNest && (
                  <div className="pointer-events-none absolute inset-x-0 top-0 z-10 rounded-t-lg bg-amber/20 px-2 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wide text-amber-deep">
                    Drop to nest as subplot
                  </div>
                )}

                <div className="flex items-center gap-1.5 px-2 py-1.5">
                  <button
                    type="button"
                    draggable
                    onDragStart={() => onReorderDragStart(t.id)}
                    onDragEnd={clearDrag}
                    aria-label="Drag to reorder"
                    className="shrink-0 cursor-grab touch-none rounded p-0.5 text-ink-muted hover:bg-ink/5 hover:text-ink-text active:cursor-grabbing"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" />
                      <circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
                      <circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" />
                    </svg>
                  </button>

                  <button
                    type="button"
                    onClick={() => toggleExpand(t.id)}
                    draggable
                    onDragStart={() => onNestDragStart(t.id)}
                    onDragEnd={clearDrag}
                    className="min-w-0 flex-1 truncate text-left font-display text-[13px] font-medium text-ink-text hover:text-amber-deep"
                    title="Click to expand subplots · drag onto another plot to nest"
                  >
                    {d.name || "Untitled"}
                  </button>

                  <span className="shrink-0 rounded bg-ink/5 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                    {d.thread_type}
                  </span>
                  {subCount > 0 && (
                    <span className="hidden shrink-0 text-[10px] text-ink-muted sm:inline" title={preview}>
                      {subCount} sub
                    </span>
                  )}

                  <button
                    type="button"
                    onClick={() => toggleExpand(t.id)}
                    className="shrink-0 rounded p-1 text-ink-muted hover:bg-ink/5"
                    aria-expanded={isOpen}
                    aria-label={isOpen ? "Collapse" : "Expand"}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                         className={`transition-transform ${isOpen ? "rotate-180" : ""}`}>
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                  </button>

                  <DeleteButton
                    label={`Delete ${t.name}`}
                    title="Delete"
                    message={`Remove "${t.name}"?`}
                    onConfirm={() => deletePlot(t)}
                    className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                  />
                </div>

                {!isOpen && preview && (
                  <p className="truncate px-8 pb-1.5 text-[11px] text-ink-muted">{preview}</p>
                )}

                {isOpen && (
                  <div className="space-y-2 border-t border-paper-line/70 px-2 pb-2 pt-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <input
                        className={`${fieldClass} min-w-[8rem] flex-1 text-[13px]`}
                        value={d.name}
                        onChange={(e) => patchDraft(t.id, { name: e.target.value })}
                        placeholder="Thread name"
                      />
                      <select
                        className={`${fieldClass} w-auto py-1 text-[11px]`}
                        value={d.thread_type}
                        onChange={(e) => patchDraft(t.id, { thread_type: e.target.value })}
                      >
                        {THREAD_TYPES.map((ty) => (
                          <option key={ty} value={ty}>{ty}</option>
                        ))}
                      </select>
                      <select
                        className={`${fieldClass} w-auto py-1 text-[11px]`}
                        value={d.status}
                        onChange={(e) => patchDraft(t.id, { status: e.target.value })}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                      <label className="flex items-center gap-0.5 text-[11px] text-ink-muted">
                        P
                        <input
                          type="number"
                          min={1}
                          max={5}
                          className={`${fieldClass} w-10 py-1 text-center text-[11px]`}
                          value={d.priority}
                          onChange={(e) => patchDraft(t.id, { priority: Number(e.target.value) })}
                        />
                      </label>
                    </div>
                    <textarea
                      className={`${fieldClass} min-h-[40px] py-1.5 text-[12px] leading-snug`}
                      value={d.description}
                      onChange={(e) => patchDraft(t.id, { description: e.target.value })}
                      placeholder="Summary for prompts"
                      rows={2}
                    />
                    <section className="rounded-lg border border-amber/30 bg-amber/5 p-2.5">
                      <label className="mb-1 block text-[11px] font-medium text-ink-muted">
                        AI direction (optional)
                      </label>
                      <textarea
                        className={`${fieldClass} mb-2 min-h-[48px] py-1.5 text-[12px] leading-snug`}
                        value={genPrompts[t.id] ?? ""}
                        onChange={(e) => setGenPrompts((p) => ({ ...p, [t.id]: e.target.value }))}
                        placeholder="Emphasize tension with X, tie in theme Y…"
                        rows={2}
                      />
                      <button
                        type="button"
                        disabled={generatingId === t.id}
                        onClick={() => void generateDescription(t.id)}
                        className="rounded-lg border border-amber/40 bg-paper-card px-3 py-1 text-[12px] font-semibold text-ink-text hover:bg-amber/10 disabled:opacity-50"
                      >
                        {generatingId === t.id ? "Generating…" : "Generate description from subplots"}
                      </button>
                      <p className="mt-1.5 text-[10px] leading-snug text-ink-muted">
                        Uses current subplots and story bible for supporting context only — does not
                        create new plots or subplots.
                      </p>
                      {(bibleSuggestions[t.id]?.length ?? 0) > 0 && (
                        <div className="mt-2 border-t border-amber/20 pt-2">
                          <p className="mb-1 text-[11px] font-medium text-ink-text">
                            Story bible suggestions (copy manually if useful)
                          </p>
                          <ul className="list-inside list-disc space-y-0.5 text-[11px] text-ink-muted">
                            {bibleSuggestions[t.id].map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </section>
                    <textarea
                      className={`${fieldClass} min-h-[56px] py-1.5 font-mono text-[11px] leading-snug`}
                      value={d.subplotsText}
                      onChange={(e) => patchDraft(t.id, { subplotsText: e.target.value })}
                      placeholder="Subplots — one per line"
                      rows={3}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
