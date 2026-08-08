import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type BinderNode } from "../api/client";
import { dropPlaceFromY, reorderIndex, type DropPlace } from "../lib/binderReorder";
import { useToast } from "./toastContext";

function statusDot(status?: string) {
  const s = (status || "").toLowerCase();
  if (s.includes("approv") || s === "final" || s === "validated") return "bg-st-approved";
  if (s.includes("edit") || s === "in_review" || s === "revised") return "bg-[var(--color-violet)]";
  if (s.includes("draft")) return "bg-st-drafted";
  return "bg-paper-muted";
}

function flattenChapters(nodes: BinderNode[]): BinderNode[] {
  const out: BinderNode[] = [];
  const walk = (list: BinderNode[]) => {
    for (const n of list) {
      if (n.type === "chapter" && n.chapter_number != null) out.push(n);
      if (n.children?.length) walk(n.children);
    }
  };
  walk(nodes);
  return out;
}

/** Chapter binder with drag + ↑/↓ reorder (PLAN.md P4). Chapter numbers stay stable. */
export default function BinderNav({
  projectId,
  activeChapter,
}: {
  projectId: string;
  activeChapter: number;
}) {
  const toast = useToast();
  const [tree, setTree] = useState<BinderNode[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropHint, setDropHint] = useState<{ id: string; place: DropPlace } | null>(null);

  const reload = useCallback(() => {
    api.binder(projectId).then(setTree).catch(() => setTree([]));
  }, [projectId]);

  useEffect(reload, [reload]);

  const chapters = useMemo(() => flattenChapters(tree), [tree]);

  async function applyMove(node: BinderNode, index: number) {
    if (!node.parent_id) return;
    setBusyId(node.id);
    try {
      const updated = await api.moveBinderNode(projectId, {
        node_id: node.id,
        parent_id: node.parent_id,
        index,
      });
      setTree(updated);
      toast("Chapter order updated", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusyId(null);
    }
  }

  async function move(node: BinderNode, direction: -1 | 1) {
    if (!node.parent_id) return;
    const siblings = chapters.filter((c) => c.parent_id === node.parent_id);
    const idx = siblings.findIndex((c) => c.id === node.id);
    const next = idx + direction;
    if (idx < 0 || next < 0 || next >= siblings.length) return;
    await applyMove(node, next);
  }

  async function dropOnto(target: BinderNode, place: DropPlace) {
    if (!draggingId || draggingId === target.id) return;
    const dragged = chapters.find((c) => c.id === draggingId);
    if (!dragged?.parent_id || dragged.parent_id !== target.parent_id) return;
    const siblings = chapters.filter((c) => c.parent_id === dragged.parent_id);
    const fromIdx = siblings.findIndex((c) => c.id === dragged.id);
    const overIdx = siblings.findIndex((c) => c.id === target.id);
    const index = reorderIndex(fromIdx, overIdx, place);
    if (index == null) return;
    await applyMove(dragged, index);
  }

  return (
    <div className="flex flex-col gap-0.5 px-2.5">
      {chapters.length === 0 && (
        <p className="px-2.5 py-2 text-[12px] text-ink-muted">No chapters yet.</p>
      )}
      {chapters.map((c) => {
        const n = c.chapter_number!;
        const active = n === activeChapter;
        const siblings = chapters.filter((x) => x.parent_id === c.parent_id);
        const localIdx = siblings.findIndex((x) => x.id === c.id);
        const canUp = localIdx > 0;
        const canDown = localIdx >= 0 && localIdx < siblings.length - 1;
        const hint = dropHint?.id === c.id ? dropHint.place : null;
        const isDragging = draggingId === c.id;

        return (
          <div
            key={c.id}
            onDragOver={(e) => {
              if (!draggingId || draggingId === c.id) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
              const place = dropPlaceFromY(e.clientY, e.currentTarget.getBoundingClientRect());
              setDropHint({ id: c.id, place });
            }}
            onDragLeave={() => {
              setDropHint((h) => (h?.id === c.id ? null : h));
            }}
            onDrop={(e) => {
              e.preventDefault();
              const place = dropHint?.id === c.id
                ? dropHint.place
                : dropPlaceFromY(e.clientY, e.currentTarget.getBoundingClientRect());
              setDropHint(null);
              void dropOnto(c, place);
            }}
            className={`group relative flex items-center gap-0.5 rounded-xl pr-0.5 transition-colors ${
              active
                ? "bg-white/70 font-medium text-ink-text shadow-[0_4px_12px_rgba(48,62,98,0.06)]"
                : "text-ink-muted hover:bg-white/45"
            } ${isDragging ? "opacity-45" : ""} ${
              hint === "before" ? "shadow-[inset_0_2px_0_0_var(--color-violet)]" : ""
            } ${hint === "after" ? "shadow-[inset_0_-2px_0_0_var(--color-violet)]" : ""}`}
          >
            <button
              type="button"
              draggable={busyId == null}
              title="Drag to reorder"
              aria-label={`Drag chapter ${n} to reorder`}
              onDragStart={(e) => {
                setDraggingId(c.id);
                e.dataTransfer.effectAllowed = "move";
                e.dataTransfer.setData("text/plain", c.id);
              }}
              onDragEnd={() => {
                setDraggingId(null);
                setDropHint(null);
              }}
              className="flex h-8 w-5 shrink-0 cursor-grab items-center justify-center rounded-lg text-[10px] leading-none tracking-tighter text-paper-muted active:cursor-grabbing hover:bg-white/70 hover:text-ink-muted"
            >
              ⋮⋮
            </button>
            <Link
              to={`/projects/${projectId}/chapters/${n}`}
              className="flex min-w-0 flex-1 items-center gap-2 py-1.5 pr-2.5 text-[13px]"
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusDot(c.status)}`} />
              <span className="nums font-mono text-[11px] text-paper-muted">{n}</span>
              <span className="truncate">{c.title || "Untitled"}</span>
            </Link>
            <div className="flex shrink-0 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <button
                type="button"
                title="Move up"
                aria-label={`Move chapter ${n} up`}
                disabled={!canUp || busyId != null}
                onClick={() => void move(c, -1)}
                className="flex h-7 w-6 items-center justify-center rounded-lg text-[11px] font-semibold text-paper-muted hover:bg-white/80 hover:text-ink disabled:opacity-25"
              >
                ↑
              </button>
              <button
                type="button"
                title="Move down"
                aria-label={`Move chapter ${n} down`}
                disabled={!canDown || busyId != null}
                onClick={() => void move(c, 1)}
                className="flex h-7 w-6 items-center justify-center rounded-lg text-[11px] font-semibold text-paper-muted hover:bg-white/80 hover:text-ink disabled:opacity-25"
              >
                ↓
              </button>
            </div>
          </div>
        );
      })}
      {chapters.length > 1 && (
        <p className="mt-1 px-2.5 text-[10.5px] leading-snug text-paper-muted">
          Drag ⋮⋮ or use ↑↓ · chapter numbers stay fixed
        </p>
      )}
    </div>
  );
}
