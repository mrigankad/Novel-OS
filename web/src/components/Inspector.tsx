import { useCallback, useEffect, useState } from "react";
import {
  api, type SnapshotMeta, type SnapshotText, type CommentItem,
} from "../api/client";
import { useToast } from "./Toaster";
import { useConfirm } from "./Confirm";
import DiffView from "./DiffView";

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function Inspector({
  id, num, currentText, flush, onRestored,
}: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText: string) => void;
}) {
  const [tab, setTab] = useState<"versions" | "comments">("versions");
  return (
    <aside className="flex w-[320px] shrink-0 flex-col overflow-y-auto border-l border-paper-line bg-paper-card/40">
      <div className="flex border-b border-paper-line">
        {(["versions", "comments"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 px-4 py-3 text-[12px] font-bold uppercase tracking-[0.12em] transition-colors ${
              tab === t ? "text-ink-text" : "text-paper-muted hover:text-ink-muted"
            }`}
          >
            {t === "versions" ? "Snapshots" : "Comments"}
            {tab === t && <span className="mt-1.5 block h-0.5 rounded-full bg-amber-deep" />}
          </button>
        ))}
      </div>
      {tab === "versions"
        ? <Snapshots id={id} num={num} currentText={currentText} flush={flush} onRestored={onRestored} />
        : <Comments id={id} num={num} />}
    </aside>
  );
}

function Snapshots({ id, num, currentText, flush, onRestored }: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText: string) => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [list, setList] = useState<SnapshotMeta[]>([]);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState<SnapshotText | null>(null);

  const reload = useCallback(() => {
    api.snapshots(id, num).then(setList).catch(() => setList([]));
  }, [id, num]);
  useEffect(reload, [reload]);

  async function saveVersion() {
    setBusy(true);
    try {
      await flush(); // persist the current buffer so the snapshot reflects it
      await api.createSnapshot(id, num, label.trim() || "Version");
      setLabel("");
      toast("Version saved", "success");
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function view(sid: string) {
    if (viewing?.id === sid) { setViewing(null); return; }
    try { setViewing(await api.getSnapshot(id, num, sid)); }
    catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  async function restore(sid: string) {
    try {
      const r = await api.restoreSnapshot(id, num, sid);
      toast("Restored — previous Final saved as a snapshot", "success");
      setViewing(null);
      onRestored(r.final);
      reload();
    } catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  async function remove(sid: string) {
    const ok = await confirm({
      title: "Delete version",
      message: "This permanently deletes this snapshot. It can't be undone.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    try { await api.deleteSnapshot(id, num, sid); reload(); if (viewing?.id === sid) setViewing(null); }
    catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="flex gap-2">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (optional)…"
          className="min-w-0 flex-1 rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-[13px] text-ink-text placeholder:text-paper-muted"
        />
        <button onClick={saveVersion} disabled={busy}
                className="shrink-0 rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
          {busy ? "Saving…" : "Save version"}
        </button>
      </div>

      {list.length === 0 && <p className="py-6 text-center text-[13px] text-ink-muted">No versions yet.</p>}

      {list.map((s) => (
        <div key={s.id} className="rounded-lg border border-paper-line bg-paper-card p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-[13.5px] font-semibold text-ink-text">{s.label}</p>
              <p className="nums text-[11.5px] text-ink-muted">{when(s.created_at)} · {s.word_count.toLocaleString()} words</p>
            </div>
          </div>
          <div className="mt-2 flex gap-3 text-[12px] font-medium">
            <button onClick={() => view(s.id)} className="text-st-drafted hover:underline">
              {viewing?.id === s.id ? "Hide diff" : "Diff"}
            </button>
            <button onClick={() => restore(s.id)} className="text-amber-deep hover:underline">Restore</button>
            <button onClick={() => remove(s.id)} className="text-ink-muted hover:text-red-600">Delete</button>
          </div>
          {viewing?.id === s.id && (
            <div className="mt-3 max-h-72 overflow-y-auto rounded-md border border-paper-line bg-paper p-3">
              <p className="mb-2 text-[10.5px] font-bold uppercase tracking-wider text-paper-muted">
                Snapshot → current
              </p>
              <DiffView oldText={viewing.text} newText={currentText} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Comments({ id, num }: { id: string; num: number }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [list, setList] = useState<CommentItem[]>([]);
  const [body, setBody] = useState("");
  const [quote, setQuote] = useState("");

  const reload = useCallback(() => {
    api.comments(id, num).then(setList).catch(() => setList([]));
  }, [id, num]);
  useEffect(reload, [reload]);

  async function removeComment(cid: string) {
    const ok = await confirm({
      title: "Delete note", message: "Delete this note?", confirmLabel: "Delete", danger: true,
    });
    if (ok) api.deleteComment(id, num, cid).then(reload).catch(() => {});
  }

  async function add() {
    if (!body.trim()) return;
    try {
      await api.addComment(id, num, body, quote);
      setBody(""); setQuote("");
      reload();
    } catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="rounded-lg border border-paper-line bg-paper-card p-3">
        <input value={quote} onChange={(e) => setQuote(e.target.value)}
               placeholder="Quote (optional)…"
               className="mb-2 w-full rounded-md border border-paper-line bg-paper px-2.5 py-1.5 text-[12.5px] text-ink-text placeholder:text-paper-muted" />
        <textarea value={body} onChange={(e) => setBody(e.target.value)}
                  placeholder="Add a note…" rows={2}
                  className="w-full resize-y rounded-md border border-paper-line bg-paper px-2.5 py-1.5 text-[13px] text-ink-text placeholder:text-paper-muted" />
        <div className="mt-2 flex justify-end">
          <button onClick={add} disabled={!body.trim()}
                  className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
            Add note
          </button>
        </div>
      </div>

      {list.length === 0 && <p className="py-6 text-center text-[13px] text-ink-muted">No notes yet.</p>}

      {list.map((c) => (
        <div key={c.id} className={`rounded-lg border border-paper-line p-3 ${c.resolved ? "bg-paper-card/50 opacity-70" : "bg-paper-card"}`}>
          {c.quote && (
            <blockquote className="mb-1.5 border-l-2 border-amber pl-2 text-[12px] italic text-ink-muted">
              “{c.quote}”
            </blockquote>
          )}
          <p className={`text-[13.5px] text-ink-text ${c.resolved ? "line-through" : ""}`}>{c.body}</p>
          <div className="mt-2 flex items-center gap-3 text-[11.5px]">
            <span className="nums text-paper-muted">{when(c.created_at)}</span>
            <button onClick={() => api.updateComment(id, num, c.id, !c.resolved).then(reload)}
                    className="font-medium text-st-approved hover:underline">
              {c.resolved ? "Reopen" : "Resolve"}
            </button>
            <button onClick={() => removeComment(c.id)}
                    className="font-medium text-ink-muted hover:text-red-600">Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}
