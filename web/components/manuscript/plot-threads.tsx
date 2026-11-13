"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Check, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { bk, bookApi, type PlotThread } from "@/lib/api/book";

const KINDS = ["main", "subplot", "mystery", "romance", "arc"] as const;

/** Plot threads on the manuscript overview: what's open, how long it's been quiet, where it should land. */
export function PlotThreads({ id, lastChapter }: { id: string; lastChapter: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const threads = useQuery({ queryKey: bk.threads(id), queryFn: () => bookApi.threads(id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["p", id, "codex"] });
  const update = useMutation({
    mutationFn: ({ tid, body }: { tid: string; body: Partial<PlotThread> }) => bookApi.updateThread(id, tid, body),
    onSuccess: refresh,
    onError: (e) => toast(String(e), "error"),
  });
  const remove = useMutation({ mutationFn: (tid: string) => bookApi.deleteThread(id, tid), onSuccess: refresh });

  const rows = [...(threads.data ?? [])].sort(
    (a, b) => Number(a.status !== "open") - Number(b.status !== "open") || a.priority - b.priority,
  );

  return (
    <section className="mt-16">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="label">Plot threads</h2>
        <p className="text-[12px] text-muted">The Guardian flags open threads that go quiet for 3+ chapters.</p>
      </div>
      <ul>
        {rows.map((t) => {
          const quiet = t.status === "open" && t.last_advanced_chapter != null ? lastChapter - t.last_advanced_chapter : null;
          const overdue = t.status === "open" && t.target_chapter != null && lastChapter > t.target_chapter;
          return (
            <li key={t.id} className={clsx("group grid grid-cols-[1fr_auto] items-center gap-3 border-b border-rule py-3.5",
              t.status !== "open" && "opacity-60")}>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={clsx("text-[16px] font-semibold text-ink", t.status === "resolved" && "line-through decoration-rule-strong")}>
                    {t.name}
                  </span>
                  <Badge>{t.kind}</Badge>
                  {overdue && <Badge tone="fail" dot>past target</Badge>}
                  {!overdue && quiet != null && quiet >= 3 && <Badge tone="warn" dot>quiet {quiet} ch</Badge>}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-body">
                  <ChapterField label="Planted" value={t.planted_chapter}
                    onChange={(v) => update.mutate({ tid: t.id, body: { planted_chapter: v } })} />
                  <ChapterField label="Last advanced" value={t.last_advanced_chapter}
                    onChange={(v) => update.mutate({ tid: t.id, body: { last_advanced_chapter: v } })} />
                  <ChapterField label="Lands by" value={t.target_chapter}
                    onChange={(v) => update.mutate({ tid: t.id, body: { target_chapter: v } })} />
                </div>
              </div>
              <div className="flex items-center gap-1">
                {t.status === "open" ? (
                  <Button size="sm" variant="ghost" onClick={() => update.mutate({ tid: t.id, body: { status: "resolved" } })}>
                    <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Resolve
                  </Button>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => update.mutate({ tid: t.id, body: { status: "open" } })}>
                    <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} /> Reopen
                  </Button>
                )}
                <button type="button" aria-label={`Delete ${t.name}`} onClick={() => remove.mutate(t.id)}
                  className="rounded-[8px] p-1.5 text-muted opacity-0 transition-opacity hover:bg-sheet hover:text-fail focus:opacity-100 group-hover:opacity-100">
                  <Trash2 className="h-4 w-4" strokeWidth={1.75} />
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      <AddThread id={id} lastChapter={lastChapter} onDone={refresh} />
    </section>
  );
}

function ChapterField({ label, value, onChange }: { label: string; value: number | null; onChange: (v: number | null) => void }) {
  return (
    <label className="inline-flex items-center gap-1.5">
      <span className="text-muted">{label}</span>
      <input
        type="number" min={1} inputMode="numeric" defaultValue={value ?? ""} placeholder="—"
        aria-label={`${label} chapter`}
        onBlur={(e) => {
          const v = e.target.value === "" ? null : Number(e.target.value);
          if (v !== value) onChange(v);
        }}
        className="w-12 rounded-[6px] border border-transparent bg-transparent px-1 py-0.5 text-ink hover:border-rule-strong focus:border-gall focus:outline-none"
      />
    </label>
  );
}

function AddThread({ id, lastChapter, onDone }: { id: string; lastChapter: number; onDone: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string>("subplot");
  const add = useMutation({
    mutationFn: () => bookApi.createThread(id, {
      name: name.trim(), kind, planted_chapter: lastChapter || null, last_advanced_chapter: lastChapter || null,
    }),
    onSuccess: () => { setName(""); onDone(); },
    onError: (e) => toast(String(e), "error"),
  });
  return (
    <form className="mt-6 flex items-center gap-3" onSubmit={(e) => { e.preventDefault(); if (name.trim()) add.mutate(); }}>
      <Plus className="h-4 w-4 shrink-0 text-muted" strokeWidth={1.75} />
      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add a plot thread…"
        className="flex-1 border-transparent px-0 hover:border-transparent focus:border-transparent" />
      <Select aria-label="Thread kind" value={kind} onChange={(v) => setKind(v)} className="w-36"
        options={KINDS.map((k) => ({ value: k as string, label: k }))} />
      <Button type="submit" variant="secondary" disabled={!name.trim() || add.isPending}>Add</Button>
    </form>
  );
}
