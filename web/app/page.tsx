"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { fmt, ProgressBar } from "@/components/manuscript/bits";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Badge, EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
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
            <Button onClick={toggle}><Plus className="h-4 w-4" strokeWidth={1.75} /> New book</Button>
          </>
        }
      />

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

      <div className="mt-10 grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
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

function BookCard({ p }: { p: Project }) {
  const pct = p.target_words ? Math.round((p.word_count / p.target_words) * 100) : 0;
  return (
    <Link href={`/p/${p.id}`} className="group flex flex-col">
      <div className="flex aspect-[3/2] items-end rounded-[16px] bg-sheet p-5 transition-colors group-hover:bg-rule">
        <BookOpen className="h-5 w-5 text-muted" strokeWidth={1.75} />
      </div>
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
