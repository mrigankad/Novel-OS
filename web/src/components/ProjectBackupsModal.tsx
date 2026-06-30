import { useCallback, useEffect, useState } from "react";
import { api, type BackupsReport, type NamedBackupMeta } from "../api/client";
import Modal from "./Modal";
import { useToast } from "./Toaster";
import { useConfirm } from "./Confirm";

function fmtWhen(iso: string | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function fmtSize(bytes: number | undefined): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProjectBackupsModal({
  projectId, open, onClose, onDone,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [report, setReport] = useState<BackupsReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [label, setLabel] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await api.backups(projectId));
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setLoading(false);
    }
  }, [projectId, toast]);

  useEffect(() => {
    if (open) {
      setLabel("");
      load();
    }
  }, [open, load]);

  async function run(action: string, fn: () => Promise<void>) {
    setBusy(action);
    try {
      await fn();
      await load();
      onDone();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(null);
    }
  }

  async function quickSave() {
    await run("quick-save", async () => {
      const r = await api.quickSaveBackup(projectId);
      toast(r.message || "Quick save complete", "success");
    });
  }

  async function quickRestore() {
    const ok = await confirm({
      title: "Quick restore",
      message: "Restore the last quick save? Your current story state will be saved first so you can undo.",
      confirmLabel: "Restore",
      danger: true,
    });
    if (!ok) return;
    await run("quick-restore", async () => {
      const r = await api.quickRestoreBackup(projectId);
      toast(r.message || "Restored from quick save", "success");
    });
  }

  async function undoRestore() {
    const ok = await confirm({
      title: "Undo restore",
      message: "Revert to the state from before your last quick restore?",
      confirmLabel: "Undo restore",
      danger: true,
    });
    if (!ok) return;
    await run("undo-restore", async () => {
      const r = await api.undoRestoreBackup(projectId);
      toast(r.message || "Restore undone", "success");
    });
  }

  async function saveNamed() {
    const name = label.trim() || `Backup ${new Date().toLocaleDateString()}`;
    await run("named-save", async () => {
      await api.createBackup(projectId, name);
      toast(`Saved backup: ${name}`, "success");
      setLabel("");
    });
  }

  async function restoreNamed(b: NamedBackupMeta) {
    const ok = await confirm({
      title: "Restore backup",
      message: `Restore "${b.label}" from ${fmtWhen(b.created_at)}? This replaces cast, plot, chapters, and story bible with that snapshot.`,
      confirmLabel: "Restore",
      danger: true,
    });
    if (!ok) return;
    await run(`restore-${b.id}`, async () => {
      const r = await api.restoreBackup(projectId, b.id);
      toast(r.message || `Restored ${b.label}`, "success");
    });
  }

  async function deleteNamed(b: NamedBackupMeta) {
    const ok = await confirm({
      title: "Delete backup",
      message: `Permanently delete "${b.label}"?`,
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    await run(`delete-${b.id}`, async () => {
      await api.deleteBackup(projectId, b.id);
      toast(`Deleted ${b.label}`, "success");
    });
  }

  const quick = report?.quick;
  const hasQuick = !!quick?.current;
  const hasUndo = !!quick?.pre_restore;

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title="Backup & restore">
      <p className="mb-5 text-[13.5px] leading-relaxed text-ink-muted">
        Saves the full story database: cast, plot threads, story bible, chapter files, and editor snapshots.
        Backups are stored inside this project folder.
      </p>

      {/* Quick save / restore */}
      <section className="mb-6 rounded-xl border border-amber/30 bg-amber/5 p-4">
        <h3 className="mb-1 text-[12px] font-bold uppercase tracking-wider text-amber-deep">
          Quick save
        </h3>
        <p className="mb-3 text-[12.5px] text-ink-muted">
          One-button checkpoint for mistakes. Quick restore saves your current state first so you can undo.
        </p>
        {quick?.current && (
          <p className="mb-3 text-[12px] text-ink-muted">
            Last quick save: {fmtWhen(quick.current.created_at)}
            {quick.current.size_bytes ? ` · ${fmtSize(quick.current.size_bytes)}` : ""}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={quickSave} disabled={!!busy}
                  className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
            {busy === "quick-save" ? "Saving…" : "Quick save"}
          </button>
          <button type="button" onClick={quickRestore} disabled={!!busy || !hasQuick}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
            {busy === "quick-restore" ? "Restoring…" : "Quick restore"}
          </button>
          {hasUndo && (
            <button type="button" onClick={undoRestore} disabled={!!busy}
                    className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
              {busy === "undo-restore" ? "Undoing…" : "Undo restore"}
            </button>
          )}
        </div>
      </section>

      {/* Named backups */}
      <section>
        <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wider text-ink-muted">
          Named backups
        </h3>
        <div className="mb-4 flex gap-2">
          <input
            className="min-w-0 flex-1 rounded-lg border border-paper-line bg-paper px-3.5 py-2.5 text-[14px] text-ink-text placeholder:text-paper-muted"
            placeholder={`Label — e.g. Before cast merge (${new Date().toLocaleDateString()})`}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") saveNamed(); }}
          />
          <button type="button" onClick={saveNamed} disabled={!!busy}
                  className="shrink-0 rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
            {busy === "named-save" ? "Saving…" : "Save backup"}
          </button>
        </div>

        {loading ? (
          <p className="py-6 text-center text-[13px] text-ink-muted">Loading…</p>
        ) : !report?.named.length ? (
          <p className="rounded-lg border border-dashed border-paper-line px-5 py-8 text-center text-[13.5px] text-ink-muted">
            No named backups yet. Save one before big edits or imports.
          </p>
        ) : (
          <ul className="flex max-h-[35vh] flex-col gap-2 overflow-y-auto pr-1">
            {report.named.map((b) => (
              <li key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-paper-line bg-paper-card px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate font-medium text-[14px] text-ink-text">{b.label}</p>
                  <p className="text-[12px] text-ink-muted">
                    {fmtWhen(b.created_at)}
                    {b.size_bytes ? ` · ${fmtSize(b.size_bytes)}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button type="button" onClick={() => restoreNamed(b)} disabled={!!busy}
                          className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
                    Restore
                  </button>
                  <button type="button" onClick={() => deleteNamed(b)} disabled={!!busy}
                          className="rounded-lg border border-red-200 px-3 py-1.5 text-[12px] font-semibold text-red-600 hover:bg-red-50 disabled:opacity-40">
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="mt-6 flex justify-end">
        <button type="button" onClick={onClose} disabled={!!busy}
                className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
          Close
        </button>
      </div>
    </Modal>
  );
}
