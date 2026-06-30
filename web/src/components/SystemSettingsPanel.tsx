import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type LlmQueueSettings,
} from "../api/client";
import { SaveStatus, formatSavedAt } from "./EditorSaveBar";
import { useConfirm } from "./Confirm";
import { useToast } from "./Toaster";

function formatSubmittedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

type DisplayRow = {
  id: string;
  label: string;
  submittedAt: string;
  chapter?: number | null;
  state: "active" | "queued";
  removable: boolean;
  reorderable: boolean;
};

function buildRows(queue: LlmQueueSettings): { active: DisplayRow[]; queued: DisplayRow[] } {
  const running = queue.running_jobs ?? [];
  const runningLabels = new Set(running.map((r) => r.label));
  const activeItems = queue.active_items ?? [];
  const queuedItems = queue.queued_items ?? [];

  const active: DisplayRow[] = [
    ...running.map((r) => ({
      id: `job-${r.job_id}`,
      label: r.label,
      submittedAt: r.started_at,
      chapter: r.chapter,
      state: "active" as const,
      removable: false,
      reorderable: false,
    })),
    ...activeItems
      .filter((a) => !runningLabels.has(a.label))
      .map((a) => ({
        id: a.id,
        label: a.label,
        submittedAt: a.submitted_at,
        chapter: a.chapter,
        state: "active" as const,
        removable: false,
        reorderable: false,
      })),
  ];

  const queued: DisplayRow[] = queuedItems.map((q) => ({
    id: q.id,
    label: q.label,
    submittedAt: q.submitted_at,
    chapter: q.chapter,
    state: "queued" as const,
    removable: true,
    reorderable: true,
  }));

  return { active, queued };
}

function chapterBadge(chapter?: number | null) {
  if (chapter == null) return null;
  return (
    <span className="shrink-0 rounded bg-sky-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-sky-300">
      Ch.{chapter}
    </span>
  );
}

export function QueueJobPopover({
  queue,
  compact = false,
  onQueueChange,
}: {
  queue: LlmQueueSettings;
  compact?: boolean;
  onQueueChange?: (q: LlmQueueSettings) => void;
}) {
  const confirm = useConfirm();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const { active, queued } = buildRows(queue);
  const hasWork = active.length > 0 || queued.length > 0;

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const applyQueue = useCallback(
    (next: LlmQueueSettings) => {
      onQueueChange?.(next);
    },
    [onQueueChange],
  );

  async function reorderQueued(ids: string[]) {
    try {
      const next = await api.reorderLlmQueue(ids);
      applyQueue(next);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function moveEntry(id: string, position: "first" | "last") {
    try {
      const next = await api.moveLlmQueueEntry(id, position);
      applyQueue(next);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function removeEntry(row: DisplayRow) {
    const ok = await confirm({
      title: "Remove from queue?",
      message: `Cancel this waiting request?\n\n${row.label}`,
      confirmLabel: "Remove",
      danger: true,
    });
    if (!ok) return;
    try {
      const next = await api.cancelLlmQueueEntry(row.id);
      applyQueue(next);
      toast("Removed from queue", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  function onDropQueued(targetId: string) {
    if (!dragId || dragId === targetId) {
      setDragId(null);
      setOverId(null);
      return;
    }
    const ids = queued.map((r) => r.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) {
      setDragId(null);
      setOverId(null);
      return;
    }
    ids.splice(from, 1);
    ids.splice(to, 0, dragId);
    setDragId(null);
    setOverId(null);
    void reorderQueued(ids);
  }

  function RowActions({ row }: { row: DisplayRow }) {
    if (!row.reorderable) return null;
    return (
      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          title="Move to front"
          onClick={() => void moveEntry(row.id, "first")}
          className="rounded px-1 py-0.5 text-[10px] text-[#9aa3b8] hover:bg-white/10 hover:text-white"
        >
          1st
        </button>
        <button
          type="button"
          title="Move to back"
          onClick={() => void moveEntry(row.id, "last")}
          className="rounded px-1 py-0.5 text-[10px] text-[#9aa3b8] hover:bg-white/10 hover:text-white"
        >
          Last
        </button>
        <button
          type="button"
          title="Remove from queue"
          onClick={() => void removeEntry(row)}
          className="rounded px-1 py-0.5 text-[10px] text-red-300 hover:bg-red-500/20"
        >
          ×
        </button>
      </div>
    );
  }

  function JobList({
    title,
    items,
  }: {
    title: string;
    items: DisplayRow[];
  }) {
    if (items.length === 0) return null;
    return (
      <div className="mb-2 last:mb-0">
        <p className="mb-1 text-[9.5px] font-bold uppercase tracking-wider text-[#9aa3b8]">{title}</p>
        <ul className="flex flex-col gap-1">
          {items.map((row) => (
            <li
              key={row.id}
              draggable={row.reorderable}
              onDragStart={() => row.reorderable && setDragId(row.id)}
              onDragEnd={() => { setDragId(null); setOverId(null); }}
              onDragOver={(e) => {
                if (!row.reorderable || !dragId) return;
                e.preventDefault();
                setOverId(row.id);
              }}
              onDrop={() => row.reorderable && onDropQueued(row.id)}
              className={`rounded-md border px-2 py-1.5 ${
                overId === row.id && dragId
                  ? "border-amber/50 bg-amber/10"
                  : "border-[#2a3348] bg-[#121826]"
              } ${dragId === row.id ? "opacity-50" : ""}`}
            >
              <div className="flex items-start gap-1.5">
                {row.reorderable && (
                  <span
                    className="mt-0.5 shrink-0 cursor-grab text-[#6b7280] active:cursor-grabbing"
                    aria-hidden="true"
                  >
                    ≡
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {chapterBadge(row.chapter)}
                    <p className="text-[11px] font-medium leading-snug text-[#e8ebf2]">{row.label}</p>
                  </div>
                  <p className="mt-0.5 text-[10px] text-[#8b93a8]">
                    {formatSubmittedAt(row.submittedAt)}
                  </p>
                </div>
                <RowActions row={row} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const summaryParts: string[] = [];
  if (active.length > 0) summaryParts.push(`${active.length} active`);
  if (queued.length > 0) summaryParts.push(`${queued.length} queued`);

  return (
    <div ref={rootRef} className="relative mt-2 inline-block max-w-full">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`cursor-pointer text-left text-[#8b93a8] underline decoration-dotted decoration-[#6b7280] underline-offset-2 hover:text-[#c8cedd] ${
          compact ? "text-[10px]" : "text-[10.5px]"
        }`}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        {hasWork ? summaryParts.join(" · ") : `${queue.active} active · ${queue.queued} queued`}
        {queue.flushed ? " · flushed" : ""}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Job queue"
          className="absolute bottom-full left-0 z-[200] mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-[#3d4659] bg-[#0a0f18] px-3 py-2.5 text-left shadow-[0_12px_32px_rgba(0,0,0,0.65)]"
        >
          <div className="max-h-64 overflow-y-auto overscroll-contain pr-0.5">
            {!hasWork ? (
              <p className="text-[11px] text-[#8b93a8]">No jobs running.</p>
            ) : (
              <>
                <JobList title="In progress" items={active} />
                <JobList title="Waiting for slot" items={queued} />
              </>
            )}
          </div>
          {queued.some((r) => r.reorderable) && (
            <p className="mt-2 border-t border-[#2a3348] pt-2 text-[9.5px] leading-snug text-[#6b7280]">
              Drag queued items to reorder · 1st/Last/× on each row
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SystemSettingsPanel() {
  const toast = useToast();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [prefix, setPrefix] = useState("");
  const [agentsDir, setAgentsDir] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [queue, setQueue] = useState<LlmQueueSettings | null>(null);
  const [busy, setBusy] = useState<null | "restart">(null);
  const [prefixDirty, setPrefixDirty] = useState(false);
  const [prefixSaving, setPrefixSaving] = useState(false);
  const [prefixLastSaved, setPrefixLastSaved] = useState<string | null>(null);
  const [concurrencyDirty, setConcurrencyDirty] = useState(false);
  const [concurrencySaving, setConcurrencySaving] = useState(false);
  const [concurrencyLastSaved, setConcurrencyLastSaved] = useState<string | null>(null);
  const prefixLoaded = useRef(false);
  const concurrencyLoaded = useRef(false);
  const savedPrefix = useRef("");
  const savedConcurrency = useRef(2);

  const refreshQueue = useCallback(() => {
    api.llmQueueSettings().then((s) => {
      setQueue(s);
      if (!concurrencyLoaded.current || !concurrencyDirty) {
        setMaxConcurrent(s.max_concurrent);
        savedConcurrency.current = s.max_concurrent;
        concurrencyLoaded.current = true;
      }
    }).catch(() => {});
  }, [concurrencyDirty]);

  const load = useCallback(() => {
    api.systemPromptSettings().then((s) => {
      setPrefix(s.prefix);
      savedPrefix.current = s.prefix;
      setAgentsDir(s.agents_dir);
      prefixLoaded.current = true;
      if (s.prefix) setPrefixLastSaved(formatSavedAt());
    }).catch(() => {});
    refreshQueue();
  }, [refreshQueue]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(refreshQueue, 2000);
    return () => window.clearInterval(timer);
  }, [refreshQueue]);

  useEffect(() => {
    if (!prefixLoaded.current || !prefixDirty) return;
    const t = window.setTimeout(() => {
      if (prefix === savedPrefix.current) {
        setPrefixDirty(false);
        return;
      }
      setPrefixSaving(true);
      api.saveSystemPromptSettings(prefix)
        .then((s) => {
          setPrefix(s.prefix);
          savedPrefix.current = s.prefix;
          setPrefixDirty(false);
          setPrefixLastSaved(formatSavedAt());
        })
        .catch((e) => toast(e instanceof Error ? e.message : String(e), "error"))
        .finally(() => setPrefixSaving(false));
    }, 700);
    return () => window.clearTimeout(t);
  }, [prefix, prefixDirty, toast]);

  useEffect(() => {
    if (!concurrencyLoaded.current || !concurrencyDirty) return;
    const n = Math.max(1, Math.min(32, maxConcurrent));
    if (Number.isNaN(n)) return;
    const t = window.setTimeout(() => {
      if (n === savedConcurrency.current) {
        setConcurrencyDirty(false);
        return;
      }
      setConcurrencySaving(true);
      api.saveLlmQueueSettings(n)
        .then((s) => {
          setQueue(s);
          setMaxConcurrent(s.max_concurrent);
          savedConcurrency.current = s.max_concurrent;
          setConcurrencyDirty(false);
          setConcurrencyLastSaved(formatSavedAt());
        })
        .catch((e) => toast(e instanceof Error ? e.message : String(e), "error"))
        .finally(() => setConcurrencySaving(false));
    }, 600);
    return () => window.clearTimeout(t);
  }, [maxConcurrent, concurrencyDirty, toast]);

  const hasWork = queue != null && (
    (queue.running_jobs?.length ?? 0) > 0
    || queue.active > 0
    || queue.queued > 0
  );

  async function restart() {
    let latest = queue;
    try {
      latest = await api.llmQueueSettings();
      setQueue(latest);
    } catch {
      /* use cached queue state */
    }

    const running = latest?.running_jobs?.length ?? 0;
    const active = latest?.active ?? 0;
    const queued = latest?.queued ?? 0;
    const jobsBusy = running > 0 || active > 0 || queued > 0;

    if (jobsBusy) {
      const parts: string[] = [];
      if (running > 0) parts.push(`${running} background job${running === 1 ? "" : "s"}`);
      if (active > 0) parts.push(`${active} active LLM call${active === 1 ? "" : "s"}`);
      if (queued > 0) parts.push(`${queued} queued LLM request${queued === 1 ? "" : "s"}`);
      const ok = await confirm({
        title: "Restart while jobs are running?",
        message: `${parts.join(", ")} will be cancelled and the server will restart. In-flight API calls may fail.`,
        confirmLabel: "Restart anyway",
        danger: true,
      });
      if (!ok) return;
    }

    setBusy("restart");
    try {
      const r = await api.restartNovelOs();
      toast(r.message, "success");
      window.setTimeout(() => window.location.reload(), 4000);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="border-t border-ink-line/70 pt-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12.5px] font-medium text-[#aab2c4] transition-colors hover:bg-ink-800 hover:text-white"
      >
        <span className="flex items-center gap-1.5">
          AI settings
          {hasWork && !open && (
            <span className="rounded-full bg-amber/25 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber">
              busy
            </span>
          )}
        </span>
        <span className="text-[10px] text-[#8b93a8]">{open ? "▾" : "▸"}</span>
      </button>

      {!open && hasWork && queue && (
        <div className="mt-1.5 px-1">
          <QueueJobPopover queue={queue} compact onQueueChange={setQueue} />
        </div>
      )}

      {open && (
        <div className="mt-2 space-y-3 px-1">
          <div>
            <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-[#8b93a8]">
              Concurrent LLM requests
            </label>
            <p className="mb-1.5 text-[10.5px] leading-relaxed text-[#8b93a8]">
              Maximum simultaneous API calls to LM Studio. Additional jobs wait in a FIFO queue.
              Click the status line for job details (screen · project · chapter · function · time).
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="number"
                min={1}
                max={32}
                value={maxConcurrent}
                onChange={(e) => {
                  setMaxConcurrent(Number(e.target.value));
                  setConcurrencyDirty(true);
                }}
                disabled={busy != null}
                className="w-20 rounded-md border border-ink-line bg-ink-800/80 px-2 py-1.5 text-[12px] text-[#d8dce8] focus:border-amber/50 focus:outline-none disabled:opacity-40"
              />
              <SaveStatus
                dirty={concurrencyDirty}
                saving={concurrencySaving}
                lastSaved={concurrencyLastSaved}
                className="text-[#aab2c4]"
              />
            </div>
            {queue && <QueueJobPopover queue={queue} onQueueChange={setQueue} />}
          </div>

          <div>
            <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-[#8b93a8]">
              Global system prefix
            </label>
            <p className="mb-1.5 text-[10.5px] leading-relaxed text-[#8b93a8]">
              Prepended to every agent system prompt before the API call. Per-agent prompts live in{" "}
              <code className="text-[10px] text-amber/90">agents/*/prompt.md</code>.
            </p>
            <textarea
              value={prefix}
              onChange={(e) => {
                setPrefix(e.target.value);
                setPrefixDirty(true);
              }}
              rows={5}
              placeholder="e.g. Always write literary past tense. No em dashes. R-rated violence OK."
              className="w-full resize-y rounded-md border border-ink-line bg-ink-800/80 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-[#d8dce8] placeholder:text-[#6b7280] focus:border-amber/50 focus:outline-none"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <SaveStatus
                dirty={prefixDirty}
                saving={prefixSaving}
                lastSaved={prefixLastSaved}
                className="text-[#aab2c4]"
              />
              <button
                type="button"
                onClick={() => void restart()}
                disabled={busy != null}
                className="rounded-md border border-ink-line px-2.5 py-1 text-[11px] font-semibold text-[#c8cedd] transition-colors hover:bg-ink-800 disabled:opacity-40"
                title="Flush the LLM queue, cancel background jobs, and restart the server"
              >
                {busy === "restart" ? "Restarting…" : "Restart (flush queue)"}
              </button>
            </div>
          </div>
          {agentsDir && (
            <p className="text-[10px] leading-relaxed text-[#6b7280]">
              Agent prompts: <span className="break-all text-[#8b93a8]">{agentsDir}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
