"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { fmt, ProgressBar } from "@/components/manuscript/bits";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Badge, EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { GettingStarted } from "@/components/getting-started";
import { ImportSheet } from "@/components/transfer/import-sheet";
import { useToast } from "@/components/ui/toast";
import { projectsApi, qk, type Project } from "@/lib/api";
import { bookApi } from "@/lib/api/book";

const GENRES = ["Literary", "Fantasy", "Science fiction", "Mystery", "Thriller", "Romance", "Historical", "Horror", "Young adult"];

export default function LibraryPage() {
  return <Suspense><Library /></Suspense>;
}

function Library() {
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const { data, isLoading, error } = useQuery({ queryKey: qk.projects, queryFn: projectsApi.list });
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [target, setTarget] = useState("90000");
  const search = useSearchParams();
  const forced = search.get("new") === "1";
  const [openState, setOpen] = useState(false);
  const open = openState || forced;
  const [importing, setImporting] = useState(false);
  const toggle = () => { if (forced) router.replace("/"); setOpen(!open); };

  const opened = (p: Project) => { void qc.invalidateQueries({ queryKey: qk.projects }); router.push(`/p/${p.id}`); };
  const create = useMutation({
    mutationFn: () => projectsApi.create({ title: title.trim(), genre, target_words: Number(target) || 90000 }),
    onSuccess: opened,
    onError: (e) => toast(String(e), "error"),
  });
  const sample = useMutation({ mutationFn: bookApi.sample, onSuccess: opened, onError: (e) => toast(String(e), "error") });

  return (
    <Page>
      <PageHeader
        eyebrow="Your workspace"
        title="Library"
        description="Every book you're writing, with the agents that remember it."
        actions={
          <>
            <Button variant="secondary" onClick={() => sample.mutate()} disabled={sample.isPending}>
              <Sparkles className="h-4 w-4" strokeWidth={1.75} /> Try the sample book
            </Button>
            <Button variant="secondary" onClick={() => setImporting(true)}>
              <FileUp className="h-4 w-4" strokeWidth={1.75} /> Import a manuscript
            </Button>
            <Button onClick={toggle}><Plus className="h-4 w-4" strokeWidth={1.75} /> New book</Button>
          </>
        }
      />

      <GettingStarted projects={data ?? []} />
      <ImportSheet open={importing} onClose={() => setImporting(false)} onDone={(p) => { setImporting(false); opened(p); }} />

      {open && (
        <form
          className="mt-8 grid gap-4 border-b border-rule pb-8 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end"
          onSubmit={(e) => { e.preventDefault(); if (title.trim()) create.mutate(); }}
        >
          <Field label="Working title"><Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="The Glass Orchard" /></Field>
          <Field label="Genre">
            <Input list="genres" value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="Literary" />
            <datalist id="genres">{GENRES.map((g) => <option key={g} value={g} />)}</datalist>
          </Field>
          <Field label="Target words"><Input inputMode="numeric" value={target} onChange={(e) => setTarget(e.target.value.replace(/\D/g, ""))} /></Field>
          <Button type="submit" disabled={!title.trim() || create.isPending}>Create book</Button>
        </form>
      )}

      <div className="mt-10 grid grid-cols-2 gap-x-8 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">
        {isLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-40" />)}
        {error && <p className="text-[14px] text-fail">Couldn&apos;t reach the Novel OS server.</p>}
        {data?.map((p) => <BookCard key={p.id} p={p} />)}
      </div>
      {data && data.length === 0 && (
        <EmptyState
          title="No books yet"
          body="Start one with a working title, or open the sample book to see how the studio works."
          action={<Button onClick={() => sample.mutate()} disabled={sample.isPending}><Sparkles className="h-4 w-4" strokeWidth={1.75} /> Open The Glass Orchard</Button>}
        />
      )}
    </Page>
  );
}

/** The book as an object: uploaded front cover, else a typeset cover in the design's colours. */
function BookCover({ p }: { p: Project }) {
  const bg = p.cover?.background || "#14131a";
  const fg = p.cover?.text || "#ffffff";
  return (
    <div className="relative aspect-[2/3] w-full overflow-hidden rounded-[6px] shadow-[0_1px_2px_rgba(20,19,26,0.08),0_12px_28px_rgba(20,19,26,0.12)] transition-transform duration-200 [transition-timing-function:var(--ease-out)] group-hover:-translate-y-1"
      style={{ background: bg, color: fg }}>
      {p.cover?.media_id ? (
        <img src={`/api/media/${p.cover.media_id}`} alt="" loading="lazy" className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full flex-col justify-between p-[9%]">
          <p className="font-display text-[clamp(18px,2.2vw,30px)] font-bold leading-[1.02] tracking-[-0.03em]">{p.title}</p>
          <div>
            <div className="mb-3 h-px w-8" style={{ background: fg, opacity: 0.4 }} />
            <p className="text-[11px] font-medium uppercase tracking-[0.14em]" style={{ opacity: 0.75 }}>
              {p.author || p.genre || "Novel OS"}
            </p>
          </div>
        </div>
      )}
      <span className="pointer-events-none absolute inset-y-0 left-0 w-[3%] bg-black/15" aria-hidden />
    </div>
  );
}

function BookCard({ p }: { p: Project }) {
  const pct = p.target_words ? Math.round((p.word_count / p.target_words) * 100) : 0;
  return (
    <Link href={`/p/${p.id}`} className="group flex flex-col">
      <BookCover p={p} />
      <div className="mt-4 flex items-start justify-between gap-3">
        <p className="font-display text-[22px] font-bold leading-tight tracking-[-0.02em] text-ink">{p.title}</p>
        <Badge>{p.status}</Badge>
      </div>
      <p className="mt-1 text-[13px] text-body">{p.genre || "No genre yet"} · {p.chapter_count} chapters</p>
      <ProgressBar className="mt-4" value={p.word_count} max={p.target_words} />
      <p className="mt-2 text-[12px] text-muted">{fmt(p.word_count)} of {fmt(p.target_words)} words · {pct}%</p>
    </Link>
  );
}
