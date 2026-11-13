"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Camera, RotateCcw } from "lucide-react";
import { use, useMemo, useState } from "react";
import { fmt } from "@/components/manuscript/bits";
import { diffStats, wordDiff } from "@/components/manuscript/word-diff";
import { Button } from "@/components/ui/button";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { bk, bookApi, type Version } from "@/lib/api/book";

const when = (iso: string) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`)
  .toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export default function VersionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const toast = useToast();
  const chapters = useQuery({ queryKey: bk.chapters(id), queryFn: () => bookApi.chapters(id) });
  const [picked, setPicked] = useState<number | null>(null);
  const n = picked ?? chapters.data?.find((c) => c.word_count > 0)?.number ?? chapters.data?.[0]?.number ?? null;
  const chapter = useQuery({ queryKey: bk.chapter(id, n ?? 0), queryFn: () => bookApi.chapter(id, n!), enabled: n !== null });
  const versions = useQuery({ queryKey: bk.versions(id, n ?? 0), queryFn: () => bookApi.versions(id, n!), enabled: n !== null });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected: Version | undefined = versions.data?.find((v) => v.id === selectedId) ?? versions.data?.[0];

  const parts = useMemo(() => (selected && chapter.data ? wordDiff(selected.text, chapter.data.text) : []), [selected, chapter.data]);
  const stats = diffStats(parts);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["p", id, "chapter"] });
  };
  const restore = useMutation({
    mutationFn: (v: Version) => bookApi.restore(id, v.id),
    onSuccess: () => { refresh(); toast("Restored. The previous text was kept as a version.", "success"); },
    onError: (e) => toast(String(e), "error"),
  });
  const snap = useMutation({
    mutationFn: () => bookApi.snapshot(id, n!, "Manual snapshot"),
    onSuccess: () => { refresh(); toast("Snapshot saved", "success"); },
  });

  return (
    <Page wide>
      <PageHeader eyebrow="History" title="Drafts and versions" description="Every snapshot and agent pass, per chapter. Compare any version with the current text and restore it."
        actions={n !== null && <Button variant="secondary" onClick={() => snap.mutate()} disabled={snap.isPending}><Camera className="h-4 w-4" strokeWidth={1.75} /> Snapshot now</Button>} />

      <div className="mt-8 flex items-center gap-3">
        <label htmlFor="chapter" className="text-[13px] font-semibold">Chapter</label>
        <select id="chapter" value={n ?? ""} onChange={(e) => { setPicked(Number(e.target.value)); setSelectedId(null); }}
          className="h-10 rounded-[10px] border border-rule-strong bg-paper px-3 text-[14px]">
          {chapters.data?.map((c) => <option key={c.id} value={c.number}>{c.number}. {c.title || "Untitled"}</option>)}
        </select>
      </div>

      {chapters.data?.length === 0 && <div className="mt-8"><EmptyState title="No chapters yet" /></div>}
      {versions.isLoading && <Skeleton className="mt-8 h-60" />}
      {versions.data && versions.data.length === 0 && (
        <div className="mt-8"><EmptyState title="No versions yet" body="Press Ctrl+S while writing to take a snapshot. Large edits are snapshotted automatically." /></div>
      )}

      {versions.data && versions.data.length > 0 && (
        <div className="mt-8 grid gap-10 lg:grid-cols-[300px_1fr]">
          <ol className="relative border-l border-rule pl-5">
            {versions.data.map((v) => (
              <li key={v.id} className="relative mb-1">
                <span className={clsx("absolute -left-[25px] top-4 h-2.5 w-2.5 rounded-full border-[1.5px]",
                  v.produced_by.startsWith("agent") ? "border-gall bg-gall" : "border-ink bg-paper", v.id === selected?.id && "bg-ink")} />
                <button type="button" onClick={() => setSelectedId(v.id)}
                  className={clsx("w-full rounded-[10px] px-3 py-2.5 text-left", v.id === selected?.id ? "bg-sheet" : "hover:bg-sheet")}>
                  <span className="block text-[14px] font-semibold text-ink">{v.note || v.kind}</span>
                  <span className="block text-[12px] text-body">{when(v.created_at)} · {fmt(v.word_count)} words · {v.produced_by}</span>
                </button>
              </li>
            ))}
          </ol>

          {selected && (
            <div className="min-w-0">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule pb-4">
                <p className="text-[13px] text-body">
                  This version compared with the current text:{" "}
                  <span className="font-semibold text-pass">+{stats.added}</span>{" "}
                  <span className="font-semibold text-fail">−{stats.removed}</span> words
                </p>
                <Button variant="secondary" size="sm" onClick={() => restore.mutate(selected)} disabled={restore.isPending || (stats.added === 0 && stats.removed === 0)}>
                  <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} /> Restore this version
                </Button>
              </div>
              <div className="prose-book mt-6 max-w-[680px] whitespace-pre-wrap">
                {parts.length === 0 && <p className="text-muted">Empty.</p>}
                {parts.map((p, i) => p.type === "same" ? <span key={i}>{p.text}</span>
                  : p.type === "add"
                    ? <ins key={i} title="In the current text" className="bg-[color-mix(in_srgb,var(--color-pass)_14%,transparent)] no-underline">{p.text}</ins>
                    : <del key={i} title="Only in this version" className="bg-[color-mix(in_srgb,var(--color-fail)_12%,transparent)] text-fail">{p.text}</del>)}
              </div>
            </div>
          )}
        </div>
      )}
    </Page>
  );
}
