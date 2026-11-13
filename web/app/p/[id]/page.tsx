"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Plus } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { fmt, ProgressBar, StatusDot } from "@/components/manuscript/bits";
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
          <ul>{rows.filter((c) => c.act === act).map((c) => <ChapterLine key={c.id} id={id} c={c} />)}</ul>
        </section>
      ))}

      <AddChapter id={id} defaultAct={acts[acts.length - 1] ?? 1} />
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

function ChapterLine({ id, c }: { id: string; c: ChapterRow }) {
  return (
    <li>
      <Link href={`/p/${id}/write/${c.number}`}
        className="group grid grid-cols-[20px_32px_1fr_auto] items-center gap-3 border-b border-rule py-3.5 sm:grid-cols-[20px_32px_1fr_160px_90px_140px]">
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
