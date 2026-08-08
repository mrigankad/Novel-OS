import { useCallback, useEffect, useState } from "react";
import {
  api, type SnapshotMeta, type SnapshotText, type CommentItem, type ContinuityFinding,
} from "../api/client";
import { useToast } from "./toastContext";
import { useConfirm } from "./confirmContext";
import DiffView from "./DiffView";
import Icon, { type IconName } from "./Icon";

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

type Tab = "versions" | "comments" | "continuity";

export default function Inspector({
  id, num, currentText, flush, onRestored, pendingComment, onPendingCommentConsumed, onClose,
  onCommentsChange, onJumpToComment,
}: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText?: string) => void;
  pendingComment?: { from: number; to: number; quote: string } | null;
  onPendingCommentConsumed?: () => void;
  onClose?: () => void;
  onCommentsChange?: (comments: CommentItem[]) => void;
  onJumpToComment?: (c: CommentItem) => void;
}) {
  const [tab, setTab] = useState<Tab>(pendingComment ? "comments" : "versions");
  // A new pending comment pulls the rail to the Comments tab. Adjusted during
  // render so the tab is already correct on the frame the selection lands.
  const [lastPending, setLastPending] = useState(pendingComment);
  if (pendingComment !== lastPending) {
    setLastPending(pendingComment);
    if (pendingComment) setTab("comments");
  }

  const tabs: { id: Tab; label: string; icon: IconName }[] = [
    { id: "versions", label: "Snapshots", icon: "history" },
    { id: "comments", label: "Comments", icon: "message-square" },
    { id: "continuity", label: "Continuity", icon: "shield-alert" },
  ];

  return (
    <aside className="glass-rail flex min-h-full w-[340px] max-w-full flex-1 flex-col overflow-y-auto border-l-0">
      <div className="flex items-center gap-1.5 border-b border-[rgba(74,91,133,0.12)] px-2.5 py-2.5">
        <div
          role="tablist"
          aria-label="Notes panel"
          className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto overflow-y-hidden rounded-full border border-[rgba(96,112,153,0.16)] bg-white/55 p-0.5 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        >
          {tabs.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={active}
                title={t.label}
                onClick={() => setTab(t.id)}
                className={`inline-flex shrink-0 items-center justify-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                  active
                    ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                    : "text-ink-muted hover:text-ink"
                }`}
              >
                <Icon name={t.icon} className="h-3 w-3 shrink-0" />
                <span className="whitespace-nowrap">{t.label}</span>
              </button>
            );
          })}
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-white/70 hover:text-ink"
            aria-label="Close notes"
            title="Close notes"
          >
            <Icon name="chevron-right" className="h-4 w-4" />
          </button>
        )}
      </div>
      {tab === "versions" && (
        <Snapshots id={id} num={num} currentText={currentText} flush={flush} onRestored={onRestored} />
      )}
      {tab === "comments" && (
        <Comments
          id={id}
          num={num}
          pendingComment={pendingComment}
          onPendingCommentConsumed={onPendingCommentConsumed}
          onCommentsChange={onCommentsChange}
          onJumpToComment={onJumpToComment}
        />
      )}
      {tab === "continuity" && <ContinuityPanel id={id} num={num} />}
    </aside>
  );
}

function Snapshots({ id, num, currentText, flush, onRestored }: {
  id: string; num: number; currentText: string;
  flush: () => Promise<void>; onRestored: (finalText?: string) => void;
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
      toast("Restored previous Final saved as a snapshot", "success");
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
                className="btn-primary shrink-0 disabled:opacity-40">
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
            <button onClick={() => restore(s.id)} className="text-ink-muted hover:underline">Restore</button>
            <button onClick={() => remove(s.id)} className="text-ink-muted hover:text-ink">Delete</button>
          </div>
          {viewing?.id === s.id && (
            <div className="mt-3 max-h-72 overflow-y-auto rounded-md border border-paper-line bg-paper p-3">
              <p className="mb-2 text-[12px] font-medium tracking-[-0.01em] text-paper-muted">
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

function Comments({ id, num, pendingComment, onPendingCommentConsumed, onCommentsChange, onJumpToComment }: {
  id: string; num: number;
  pendingComment?: { from: number; to: number; quote: string } | null;
  onPendingCommentConsumed?: () => void;
  onCommentsChange?: (comments: CommentItem[]) => void;
  onJumpToComment?: (c: CommentItem) => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [list, setList] = useState<CommentItem[]>([]);
  const [body, setBody] = useState("");
  const [quote, setQuote] = useState("");
  const [fromPos, setFromPos] = useState<number | null>(null);
  const [toPos, setToPos] = useState<number | null>(null);
  const [persona, setPersona] = useState<"author" | "editor" | "beta">(() => {
    const raw = localStorage.getItem("novelos-comment-persona");
    return raw === "editor" || raw === "beta" ? raw : "author";
  });

  const reload = useCallback(() => {
    api.comments(id, num).then((items) => {
      setList(items);
      onCommentsChange?.(items);
    }).catch(() => setList([]));
  }, [id, num, onCommentsChange]);
  useEffect(reload, [reload]);

  // Seed the draft note from the editor selection during render; only the
  // parent notification stays in an effect, since telling another component to
  // update mid-render is illegal.
  const [lastPending, setLastPending] = useState(pendingComment);
  if (pendingComment !== lastPending) {
    setLastPending(pendingComment);
    if (pendingComment) {
      setQuote(pendingComment.quote);
      setFromPos(pendingComment.from);
      setToPos(pendingComment.to);
    }
  }

  useEffect(() => {
    if (pendingComment) onPendingCommentConsumed?.();
  }, [pendingComment, onPendingCommentConsumed]);

  async function removeComment(cid: string) {
    const ok = await confirm({
      title: "Delete note", message: "Delete this note?", confirmLabel: "Delete", danger: true,
    });
    if (ok) api.deleteComment(id, num, cid).then(reload).catch(() => {});
  }

  async function add() {
    if (!body.trim()) return;
    try {
      await api.addComment(id, num, body, quote, fromPos, toPos, persona);
      setBody(""); setQuote(""); setFromPos(null); setToPos(null);
      reload();
    } catch (e) { toast(e instanceof Error ? e.message : String(e), "error"); }
  }

  const personas: { id: "author" | "editor" | "beta"; label: string }[] = [
    { id: "author", label: "Author" },
    { id: "editor", label: "Editor" },
    { id: "beta", label: "Beta" },
  ];

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="rounded-2xl border border-[rgba(74,91,133,0.12)] bg-white/70 p-3">
        <div className="mb-2 flex overflow-hidden rounded-full border border-[rgba(96,112,153,0.16)] bg-white/80 p-0.5">
          {personas.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                setPersona(p.id);
                localStorage.setItem("novelos-comment-persona", p.id);
              }}
              className={`flex-1 rounded-full px-2 py-1 text-[11px] font-medium transition-colors ${
                persona === p.id
                  ? "bg-[var(--color-violet)] text-white"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <input value={quote} onChange={(e) => setQuote(e.target.value)}
               placeholder="Quote (optional)…"
               className="mb-2 w-full rounded-xl border border-[rgba(96,112,153,0.16)] bg-white/80 px-2.5 py-1.5 text-[12.5px] text-ink-text placeholder:text-paper-muted" />
        {fromPos != null && toPos != null && (
          <p className="mb-2 text-[11px] text-ink-muted">Anchored · chars {fromPos}–{toPos}</p>
        )}
        <textarea value={body} onChange={(e) => setBody(e.target.value)}
                  placeholder={`Add a ${persona} note…`} rows={2}
                  className="w-full resize-y rounded-xl border border-[rgba(96,112,153,0.16)] bg-white/80 px-3 py-2.5 text-[13px] leading-relaxed text-ink-text placeholder:text-paper-muted" />
        <div className="mt-2 flex justify-end">
          <button type="button" onClick={add} disabled={!body.trim()}
                  className="btn-primary disabled:opacity-40">
            Add note
          </button>
        </div>
      </div>

      {list.length === 0 && <p className="py-6 text-center text-[13px] text-ink-muted">No notes yet.</p>}

      {list.map((c) => (
        <div key={c.id} className={`rounded-2xl border border-[rgba(74,91,133,0.12)] p-3 ${c.resolved ? "bg-white/40 opacity-70" : "bg-white/70"}`}>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-violet)]">
            {c.persona || "author"}
          </p>
          {c.quote && (
            <blockquote className="mb-1.5 border-l-2 border-[var(--color-violet)] pl-2 text-[12px] italic text-ink-muted">
              “{c.quote}”
            </blockquote>
          )}
          {c.anchor_status === "unresolved" && (
            <p className="mb-1 text-[11px] font-medium text-[#c85177]">Anchor unresolved</p>
          )}
          <p className={`text-[13.5px] text-ink-text ${c.resolved ? "line-through" : ""}`}>{c.body}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11.5px]">
            <span className="nums text-paper-muted">{when(c.created_at)}</span>
            {c.from_pos != null && c.to_pos != null && c.anchor_status !== "unresolved" && (
              <button type="button" onClick={() => onJumpToComment?.(c)}
                      className="font-medium text-[var(--color-violet)] hover:underline">
                Show
              </button>
            )}
            <button type="button" onClick={() => api.updateComment(id, num, c.id, !c.resolved).then(reload)}
                    className="font-medium text-st-approved hover:underline">
              {c.resolved ? "Reopen" : "Resolve"}
            </button>
            <button type="button" onClick={() => removeComment(c.id)}
                    className="font-medium text-ink-muted hover:text-ink">Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * "This is intentional" (PLAN.md P2.1).
 *
 * A checker cannot tell an unreliable narrator or a character who lies from a
 * real mistake, so the writer needs a third answer besides fixing and ignoring.
 * The reason is required in spirit but not enforced: asking for it is what makes
 * the exemption reviewable six months later, but blocking on it would just
 * teach people to type "x".
 */
function IntentionalButton({
  projectId, finding, onExempted,
}: {
  projectId: string;
  finding: ContinuityFinding;
  onExempted: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await api.exemptFinding(projectId, finding.key, reason);
      toast("Marked intentional — it won't be raised again", "success");
      setOpen(false);
      setReason("");
      onExempted();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="btn-ghost mt-2 px-2 py-0.5 text-[11.5px]"
        onClick={() => setOpen(true)}
      >
        This is intentional
      </button>
    );
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <input
        autoFocus
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") void submit();
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Why? e.g. she lies about it"
        aria-label="Why is this intentional?"
        className="min-w-0 flex-1 rounded-lg border border-[rgba(96,112,153,0.2)] bg-white/80 px-2 py-1 text-[12px] text-ink-text"
      />
      <button type="button" className="btn-ghost px-2 py-0.5 text-[11.5px]"
              onClick={() => setOpen(false)}>
        Cancel
      </button>
      <button type="button" disabled={busy}
              className="btn-secondary px-2 py-0.5 text-[11.5px] disabled:opacity-40"
              onClick={() => void submit()}>
        {busy ? "Saving…" : "Dismiss"}
      </button>
    </div>
  );
}

function ContinuityPanel({ id, num }: { id: string; num: number }) {
  const [findings, setFindings] = useState<ContinuityFinding[] | null>(null);
  const [counts, setCounts] = useState({ critical: 0, warning: 0, info: 0 });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.chapterContinuity(id, num)
      .then((r) => {
        setFindings(r.findings);
        setCounts({ critical: r.critical, warning: r.warning, info: r.info });
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [id, num]);

  useEffect(() => { load(); }, [load]);

  const iconFor = (sev: string): IconName => {
    if (sev === "critical") return "circle-alert";
    if (sev === "warning") return "triangle-alert";
    return "circle-check";
  };

  return (
    <div className="flex flex-col gap-3 px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] text-ink-muted">
          Deterministic checks free and instant.
        </p>
        <button type="button" onClick={load} className="btn-ghost text-[12px]">Refresh</button>
      </div>
      {findings && (
        <div className="flex gap-2 text-[11px]">
          <span className="rounded-full bg-[#ffeaf1] px-2 py-0.5 text-[#c85177]">{counts.critical} critical</span>
          <span className="rounded-full bg-[#fff2dc] px-2 py-0.5 text-[#c47a1b]">{counts.warning} warning</span>
          <span className="rounded-full bg-[#e8f1ff] px-2 py-0.5 text-[#3974db]">{counts.info} info</span>
        </div>
      )}
      {error && <p className="text-[13px] text-[#c85177]">{error}</p>}
      {!error && !findings && <p className="py-6 text-center text-[13px] text-ink-muted">Running checks…</p>}
      {findings && findings.length === 0 && (
        <p className="py-8 text-center text-[13px] text-ink-muted">No continuity findings.</p>
      )}
      {findings?.map((f, i) => (
        <div key={`${f.category}-${i}`} className="rounded-2xl border border-[rgba(74,91,133,0.12)] bg-white/70 p-3">
          <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium capitalize text-ink-muted">
            <Icon name={iconFor(f.severity)} className="h-3.5 w-3.5" />
            {f.severity} · {f.category.replace(/_/g, " ")}
            {f.chapter != null && <> · Ch {f.chapter}</>}
          </div>
          <p className="text-[13px] text-ink-text">{f.message}</p>
          {f.suggestion && (
            <p className="mt-1.5 text-[12px] text-ink-muted">{f.suggestion}</p>
          )}
          {f.key && (
            <IntentionalButton
              projectId={id}
              finding={f}
              onExempted={load}
            />
          )}
        </div>
      ))}
    </div>
  );
}
