"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { projectsApi, qk } from "@/lib/api";

// Owner: manuscript agent (extend with covers, progress, search). Foundation version.
export default function LibraryPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const { data, isLoading, error } = useQuery({ queryKey: qk.projects, queryFn: projectsApi.list });
  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () => projectsApi.create({ title: title.trim() }),
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: qk.projects }); router.push(`/p/${p.id}`); },
    onError: (e) => toast(String(e), "error"),
  });

  return (
    <Page>
      <PageHeader eyebrow="Your workspace" title="Library" description="Every book you're writing, with the agents that remember it." />
      <form className="mt-8 flex items-end gap-3" onSubmit={(e) => { e.preventDefault(); if (title.trim()) create.mutate(); }}>
        <div className="flex-1"><Field label="New book"><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Working title" /></Field></div>
        <Button type="submit" disabled={!title.trim() || create.isPending}><Plus className="h-4 w-4" /> Create</Button>
      </form>
      <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}
        {error && <p className="text-[14px] text-fail">Couldn&apos;t reach the Novel OS server on port 8000.</p>}
        {data?.map((p) => (
          <Link key={p.id} href={`/p/${p.id}`} className="rounded-[16px] border border-rule p-5 transition-colors hover:border-rule-strong">
            <p className="font-display text-[20px] font-bold tracking-[-0.02em]">{p.title}</p>
            <p className="mt-1 text-[13px] text-body">{p.genre || "No genre yet"} · {p.chapter_count} chapters · {p.word_count.toLocaleString()} words</p>
          </Link>
        ))}
      </div>
      {data && data.length === 0 && <div className="mt-2"><EmptyState title="No books yet" body="Give your first one a working title above." /></div>}
    </Page>
  );
}
