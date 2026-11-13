"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ChevronDown, ChevronUp, GripVertical, Plus } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { fmt, ProgressBar, StatusDot } from "@/components/manuscript/bits";
import { PlotThreads } from "@/components/manuscript/plot-threads";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { EmptyState, Page, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { projectsApi, qk } from "@/lib/api";
import { actLabel, bk, bookApi, type ChapterRow } from "@/lib/api/book";

export default function ManuscriptPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const project = useQuery({ queryKey: qk.project(id), queryFn: () => projectsApi.get(id) });
  const chapters = useQuery({ queryKey: bk.chapters(id), queryFn: () => bookApi.chapters(id) });
  const rows = chapters.data ?? [];
  const reorder = useReorder(id, rows);
  const [dragId, setDragId] = useState<string | null>(null);
  const lastWritten = rows.filter((c) => c.word_count > 0).reduce((m, c) => Math.max(m, c.number), 0);
  const acts = [...new Set(rows.map((c) => c.act))].sort((a, b) => a - b);
  const p = project.data;
  const counts = {
    planned: rows.filter((c) => c.status === "planned").length,
    drafted: rows.filter((c) => !["planned", "final"].includes(c.status)).length,
    final: rows.filter((c) => c.status === "final").length,
  };

  return (
    <Page>
      {p ? (
        <header>
          <p className="eyebrow mb-3">{p.genre || "Manuscript"}</p>
          <h1 className="font-display text-[56px] font-bold leading-[1] tracking-[-0.035em] text-ink">{p.title}</h1>
          {p.premise && <p className="mt-5 max-w-2xl font-prose text-[19px] leading-[1.6] text-body">{p.premise}</p>}
        </header>
      ) : <Skeleton className="h-32" />}

      {p && (
        <section className="mt-10 grid gap-6 border-y border-rule py-6 sm:grid-cols-[2fr_1fr_1fr_1fr]">
          <div>
            <p className="font-display text-[28px] font-bold tracking-[-0.02em]">{fmt(p.word_count)}</p>
            <p className="text-[13px] text-body">of {fmt(p.target_words)} words</p>
            <ProgressBar className="mt-3" value={p.word_count} max={p.target_words} />
          </div>
          <Stat n={counts.planned} label="planned" status="planned" />
          <Stat n={counts.drafted} label="drafted" status="drafted" />
          <Stat n={counts.final} label="final" status="final" />
        </section>
      )}

      {chapters.isLoading && <div className="mt-10 space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
      {chapters.data && rows.length === 0 && (
        <div className="mt-10"><EmptyState title="No chapters yet" body="Add the first one below. You can plan it before you write it." /></div>
      )}

      {acts.map((act) => (
        <section key={act} className="mt-12">
          <h2 className="label mb-2">{actLabel(act)}</h2>
          <ul>
            {rows.filter((c) => c.act === act).map((c) => (
              <ChapterLine key={c.id} id={id} c={c}
                dragging={dragId === c.id}
                onDragStart={() => setDragId(c.id)}
                onDragEnd={() => setDragId(null)}
                onDropOn={() => { if (dragId && dragId !== c.id) reorder.moveTo(dragId, c.id); setDragId(null); }}
                onMove={(delta) => reorder.moveBy(c.id, delta)}
                isFirst={c.id === rows[0]?.id} isLast={c.id === rows[rows.length - 1]?.id} />
            ))}
          </ul>
        </section>
      ))}

      <AddChapter id={id} defaultAct={acts[acts.length - 1] ?? 1} />

      {rows.length > 0 && <PlotThreads id={id} lastChapter={lastWritten} />}
    </Page>
  );
}

function Stat({ n, label, status }: { n: number; label: string; status: string }) {
  return (
    <div>
      <p className="font-display text-[28px] font-bold tracking-[-0.02em]">{n}</p>
      <p className="flex items-center gap-2 text-[13px] text-body"><StatusDot status={status} /> {label}</p>
    </div>
  );
}

/** Reordering: optimistic, then the server renumbers. Order is global across acts. */
function useReorder(id: string, rows: ChapterRow[]) {
  const qc = useQueryClient();
  const toast = useToast();
  const save = useMutation({
    mutationFn: (order: string[]) => bookApi.reorder(id, order),
    onMutate: async (order) => {
      await qc.cancelQueries({ queryKey: bk.chapters(id) });
      const prev = qc.getQueryData<ChapterRow[]>(bk.chapters(id));
      const byId = new Map(rows.map((r) => [r.id, r]));
      qc.setQueryData(bk.chapters(id), order.map((oid, i) => ({ ...byId.get(oid)!, number: i + 1 })));
      return { prev };
    },
    onError: (e, _o, ctx) => { if (ctx?.prev) qc.setQueryData(bk.chapters(id), ctx.prev); toast(String(e), "error"); },
    onSettled: () => qc.invalidateQueries({ queryKey: ["p", id, "chapter"] }),
  });
  const ids = rows.map((r) => r.id);
  return {
    moveTo(from: string, to: string) {
      const next = ids.filter((x) => x !== from);
      next.splice(next.indexOf(to) + (ids.indexOf(from) < ids.indexOf(to) ? 1 : 0), 0, from);
      save.mutate(next);
    },
    moveBy(cid: string, delta: number) {
      const i = ids.indexOf(cid), j = i + delta;
      if (j < 0 || j >= ids.length) return;
      const next = [...ids];
      [next[i], next[j]] = [next[j], next[i]];
      save.mutate(next);
    },
  };
}

function ChapterLine({ id, c, dragging, onDragStart, onDragEnd, onDropOn, onMove, isFirst, isLast }: {
  id: string; c: ChapterRow; dragging: boolean; onDragStart: () => void; onDragEnd: () => void;
  onDropOn: () => void; onMove: (delta: number) => void; isFirst: boolean; isLast: boolean;
}) {
  const [over, setOver] = useState(false);
  return (
    <li
      draggable
      onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; onDragStart(); }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onDropOn(); }}
      className={`group/row relative flex items-center ${dragging ? "opacity-40" : ""} ${over ? "shadow-[inset_0_2px_0_var(--color-gall)]" : ""}`}
    >
      <span className="absolute -left-14 flex items-center opacity-0 transition-opacity group-hover/row:opacity-100 focus-within:opacity-100">
        <GripVertical className="h-4 w-4 cursor-grab text-muted" strokeWidth={1.75} aria-hidden />
        <span className="flex flex-col">
          <button type="button" aria-label={`Move chapter ${c.number} up`} disabled={isFirst} onClick={() => onMove(-1)}
            className="rounded p-0.5 text-muted hover:text-ink disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
          <button type="button" aria-label={`Move chapter ${c.number} down`} disabled={isLast} onClick={() => onMove(1)}
            className="rounded p-0.5 text-muted hover:text-ink disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
        </span>
      </span>
      <Link href={`/p/${id}/write/${c.number}`} draggable={false}
        className="group grid w-full grid-cols-[20px_32px_1fr_auto] items-center gap-3 border-b border-rule py-3.5 sm:grid-cols-[20px_32px_1fr_160px_90px_140px]">
        <StatusDot status={c.status} />
        <span className="text-[13px] text-muted">{c.number}</span>
        <span className="min-w-0">
          <span className="block truncate text-[16px] font-semibold text-ink group-hover:underline">{c.title || "Untitled"}</span>
          {c.synopsis && <span className="block truncate text-[13px] text-body">{c.synopsis}</span>}
        </span>
        <span className="hidden truncate text-[13px] text-body sm:block">{c.pov || "No POV"}</span>
        <span className="text-right text-[13px] text-body">{c.word_count ? fmt(c.word_count) : "—"}</span>
        <span className="hidden items-center justify-end gap-1.5 text-[12px] sm:flex">
          {c.assigned_agent_name
            ? <><Bot className="h-3.5 w-3.5 text-gall" strokeWidth={1.75} /><span className="truncate text-gall">{c.assigned_agent_name}</span></>
            : <span className="text-muted">Unassigned</span>}
        </span>
      </Link>
    </li>
  );
}

function AddChapter({ id, defaultAct }: { id: string; defaultAct: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [act, setAct] = useState<number | null>(null);
  const add = useMutation({
    mutationFn: () => bookApi.createChapter(id, { title: title.trim(), act: act ?? defaultAct }),
    onSuccess: () => {
      setTitle("");
      void qc.invalidateQueries({ queryKey: ["p", id, "chapter"] });
      void qc.invalidateQueries({ queryKey: qk.project(id), exact: true });
    },
    onError: (e) => toast(String(e), "error"),
  });
  return (
    <form className="mt-8 flex items-center gap-3" onSubmit={(e) => { e.preventDefault(); if (title.trim()) add.mutate(); }}>
      <Plus className="h-4 w-4 shrink-0 text-muted" strokeWidth={1.75} />
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Add a chapter…" className="flex-1 border-transparent px-0 hover:border-transparent focus:border-transparent" />
      <select aria-label="Act" value={act ?? defaultAct} onChange={(e) => setAct(Number(e.target.value))}
        className="h-10 rounded-[10px] border border-rule-strong bg-paper px-2 text-[13px]">
        {[1, 2, 3, 4, 5].map((a) => <option key={a} value={a}>{actLabel(a)}</option>)}
      </select>
      <Button type="submit" variant="secondary" disabled={!title.trim() || add.isPending}>Add</Button>
    </form>
  );
}
