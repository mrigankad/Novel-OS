import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { api, type BinderNode, type ChapterSummary } from "../api/client";
import { dropPlaceFromY, reorderIndex, type DropPlace } from "../lib/binderReorder";
import type { ChapterContinuityBadge } from "../lib/chapterBadges";
import StatusPill from "./StatusPill";
import Icon from "./Icon";
import { useToast } from "./toastContext";

const grid = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } };
const card = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.2, 0.8, 0.2, 1] as const } },
};

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

function sceneFallback(node: BinderNode): string {
  const scenes = (node.children || []).filter((c) => c.type === "scene" && (c.synopsis || "").trim());
  if (!scenes.length) return "";
  return scenes.map((s) => s.synopsis!.trim()).join(" · ");
}

/** Corkboard: synopsis cards in binder order with drag + inline edit (P4.2). */
export default function ChapterBoard({
  chapters,
  continuityBadges,
}: {
  chapters: ChapterSummary[];
  continuityBadges?: Record<number, ChapterContinuityBadge>;
}) {
  const { id = "" } = useParams();
  const toast = useToast();
  const [tree, setTree] = useState<BinderNode[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropHint, setDropHint] = useState<{ id: string; place: DropPlace } | null>(null);

  const byNumber = useMemo(() => {
    const m = new Map<number, ChapterSummary>();
    for (const c of chapters) m.set(c.number, c);
    return m;
  }, [chapters]);

  const reload = useCallback(() => {
    if (!id) return;
    api.binder(id).then((t) => {
      setTree(t);
      const next: Record<string, string> = {};
      for (const n of flattenChapters(t)) {
        next[n.id] = (n.synopsis || "").trim() || sceneFallback(n);
      }
      setDrafts(next);
    }).catch(() => setTree([]));
  }, [id]);

  useEffect(reload, [reload]);

  const cards = useMemo(() => flattenChapters(tree), [tree]);

  async function saveSynopsis(node: BinderNode) {
    if (!id) return;
    const text = (drafts[node.id] ?? "").trim();
    const prior = (node.synopsis || "").trim();
    if (text === prior) return;
    setBusyId(node.id);
    try {
      const updated = await api.patchBinderNode(id, node.id, { synopsis: text });
      setTree(updated);
      toast("Synopsis saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusyId(null);
    }
  }

  async function applyMove(node: BinderNode, index: number) {
    if (!id || !node.parent_id) return;
    setBusyId(node.id);
    try {
      const updated = await api.moveBinderNode(id, {
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
    const siblings = cards.filter((c) => c.parent_id === node.parent_id);
    const idx = siblings.findIndex((c) => c.id === node.id);
    const next = idx + direction;
    if (idx < 0 || next < 0 || next >= siblings.length) return;
    await applyMove(node, next);
  }

  async function dropOnto(target: BinderNode, place: DropPlace) {
    if (!draggingId || draggingId === target.id) return;
    const dragged = cards.find((c) => c.id === draggingId);
    if (!dragged?.parent_id || dragged.parent_id !== target.parent_id) return;
    const siblings = cards.filter((c) => c.parent_id === dragged.parent_id);
    const fromIdx = siblings.findIndex((c) => c.id === dragged.id);
    const overIdx = siblings.findIndex((c) => c.id === target.id);
    const index = reorderIndex(fromIdx, overIdx, place);
    if (index == null) return;
    await applyMove(dragged, index);
  }

  async function refreshSynopsis(node: BinderNode) {
    if (!id || node.chapter_number == null) return;
    setBusyId(node.id);
    try {
      const r = await api.refreshSynopsis(id, node.chapter_number);
      setDrafts((d) => ({ ...d, [node.id]: r.synopsis }));
      const updated = await api.binder(id);
      setTree(updated);
      toast(
        r.source === "architect" ? "Synopsis refreshed" : "Synopsis drafted from outline",
        "success",
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusyId(null);
    }
  }

  if (chapters.length === 0 && cards.length === 0) {
    return (
      <div className="rounded-[24px] border border-dashed border-[rgba(74,91,133,0.18)] bg-white/45 px-8 py-12 text-center">
        <p className="font-display text-[16px] tracking-[-0.02em] text-ink-text">No chapters planned yet</p>
        <p className="mt-2 text-[12.5px] text-ink-muted">
          Plan one with <code className="font-mono text-[11px]">plan chapter --number 1</code>
        </p>
      </div>
    );
  }

  const display = cards.length > 0
    ? cards
    : chapters.map((c) => ({
        id: `fallback-${c.number}`,
        type: "chapter",
        title: c.title,
        chapter_number: c.number,
        synopsis: "",
        status: c.status,
        pov: c.pov,
        word_count: c.word_count,
        parent_id: null,
        children: [],
      } as BinderNode));

  return (
    <div>
      <p className="mb-3 text-[12.5px] text-ink-muted">
        Corkboard · edit synopses · drag cards or use ↑↓ to reorder
      </p>
      <motion.div
        variants={grid}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"
      >
        {display.map((node) => {
          const n = node.chapter_number ?? 0;
          const meta = byNumber.get(n);
          const badge = continuityBadges?.[n];
          const siblings = display.filter((x) => x.parent_id === node.parent_id);
          const localIdx = siblings.findIndex((x) => x.id === node.id);
          const canUp = localIdx > 0;
          const canDown = localIdx >= 0 && localIdx < siblings.length - 1;
          const editable = Boolean(node.id && !String(node.id).startsWith("fallback-"));
          const hint = dropHint?.id === node.id ? dropHint.place : null;
          const isDragging = draggingId === node.id;

          return (
            <motion.div
              key={node.id}
              variants={card}
              onDragOver={(e) => {
                if (!editable || !draggingId || draggingId === node.id) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                const place = dropPlaceFromY(e.clientY, e.currentTarget.getBoundingClientRect());
                setDropHint({ id: node.id, place });
              }}
              onDragLeave={() => {
                setDropHint((h) => (h?.id === node.id ? null : h));
              }}
              onDrop={(e) => {
                if (!editable) return;
                e.preventDefault();
                const place = dropHint?.id === node.id
                  ? dropHint.place
                  : dropPlaceFromY(e.clientY, e.currentTarget.getBoundingClientRect());
                setDropHint(null);
                void dropOnto(node, place);
              }}
              className={`glass-card relative flex flex-col p-4 ${
                isDragging ? "opacity-45" : ""
              } ${hint === "before" ? "ring-2 ring-[var(--color-violet)] ring-offset-2" : ""} ${
                hint === "after" ? "ring-2 ring-[var(--color-violet)]/70 ring-offset-2" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  {editable && (
                    <button
                      type="button"
                      draggable={busyId == null}
                      title="Drag to reorder"
                      aria-label={`Drag chapter ${n} to reorder`}
                      onDragStart={(e) => {
                        setDraggingId(node.id);
                        e.dataTransfer.effectAllowed = "move";
                        e.dataTransfer.setData("text/plain", node.id);
                      }}
                      onDragEnd={() => {
                        setDraggingId(null);
                        setDropHint(null);
                      }}
                      className="flex h-6 w-5 cursor-grab items-center justify-center rounded-md text-[10px] tracking-tighter text-paper-muted active:cursor-grabbing hover:bg-white/80 hover:text-ink-muted"
                    >
                      ⋮⋮
                    </button>
                  )}
                  <span className="text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
                    Chapter {n || "—"}
                  </span>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-1.5">
                  {badge && (badge.critical > 0 || badge.warning > 0) && (
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-medium ${
                        badge.critical > 0
                          ? "bg-[#ffeaf1] text-[#c85177]"
                          : "bg-[#fff2dc] text-[#c47a1b]"
                      }`}
                      title="Continuity findings"
                    >
                      <Icon
                        name={badge.critical > 0 ? "shield-alert" : "triangle-alert"}
                        className="h-3 w-3"
                      />
                      {badge.critical > 0
                        ? `${badge.critical} critical`
                        : `${badge.warning} warning`}
                    </span>
                  )}
                  <StatusPill status={meta?.status || node.status || "planned"} />
                </div>
              </div>

              <Link
                to={`/projects/${id}/chapters/${n}`}
                className="mt-2.5 font-display text-[17px] font-semibold leading-snug tracking-[-0.02em] text-ink-text transition-colors hover:text-[var(--color-violet)]"
              >
                {node.title || meta?.title || "Untitled"}
              </Link>

              <textarea
                value={drafts[node.id] ?? node.synopsis ?? ""}
                disabled={!editable || busyId === node.id}
                onChange={(e) => setDrafts((d) => ({ ...d, [node.id]: e.target.value }))}
                onBlur={() => { if (editable) void saveSynopsis(node); }}
                placeholder="Add a synopsis…"
                rows={4}
                className="mt-3 w-full resize-y rounded-xl border border-[rgba(96,112,153,0.14)] bg-white/70 px-3 py-2.5 text-[13px] leading-relaxed text-ink-text placeholder:text-paper-muted focus:border-[rgba(104,103,234,0.45)] focus:outline-none disabled:opacity-60"
              />

              <div className="mt-2 flex items-center justify-between gap-2">
                <button
                  type="button"
                  disabled={!editable || busyId != null}
                  onClick={() => void refreshSynopsis(node)}
                  className="rounded-full border border-[rgba(96,112,153,0.16)] bg-white/70 px-2.5 py-1 text-[11px] font-medium text-ink-muted transition-colors hover:text-[var(--color-violet)] disabled:opacity-40"
                  title="Architect writes a corkboard synopsis"
                >
                  {busyId === node.id ? "Refreshing…" : "Refresh with Architect"}
                </button>
                {editable && (
                  <div className="flex shrink-0">
                    <button
                      type="button"
                      title="Move earlier"
                      aria-label={`Move chapter ${n} up`}
                      disabled={!canUp || busyId != null}
                      onClick={() => void move(node, -1)}
                      className="flex h-7 w-6 items-center justify-center rounded-lg text-[11px] font-semibold hover:bg-white/80 disabled:opacity-25"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      title="Move later"
                      aria-label={`Move chapter ${n} down`}
                      disabled={!canDown || busyId != null}
                      onClick={() => void move(node, 1)}
                      className="flex h-7 w-6 items-center justify-center rounded-lg text-[11px] font-semibold hover:bg-white/80 disabled:opacity-25"
                    >
                      ↓
                    </button>
                  </div>
                )}
              </div>

              <div className="mt-3 flex items-center gap-2 text-[11.5px] text-ink-muted">
                <span className="nums">
                  {(meta?.word_count ?? node.word_count ?? 0).toLocaleString()} words
                </span>
                {(meta?.pov || node.pov) && (
                  <>
                    <span className="text-paper-muted">·</span>
                    <span className="truncate">POV {meta?.pov || node.pov}</span>
                  </>
                )}
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
