"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Plus, Search, Trash2, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, use, useMemo, useState } from "react";
import { ProposalsStrip } from "@/components/transfer/proposals-strip";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { bk, bookApi, type CodexEntry } from "@/lib/api/book";

const TABS = [
  { kind: "", label: "All" },
  { kind: "character", label: "Characters" },
  { kind: "location", label: "Places" },
  { kind: "item", label: "Items" },
  { kind: "lore", label: "Lore" },
  { kind: "faction", label: "Factions" },
  { kind: "event", label: "Events" },
  { kind: "theme", label: "Themes" },
];
const kindLabel = (k: string) => TABS.find((t) => t.kind === k)?.label.replace(/s$/, "") ?? k;

export default function CodexPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Suspense><Codex id={id} /></Suspense>;
}

function Codex({ id }: { id: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const router = useRouter();
  const search = useSearchParams();
  const selected = search.get("entry");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const all = useQuery({ queryKey: bk.codex(id), queryFn: () => bookApi.codex(id) });
  const entries = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (all.data ?? []).filter((e) => (!kind || e.kind === kind)
      && (!needle || e.name.toLowerCase().includes(needle) || e.aliases.some((a) => a.toLowerCase().includes(needle))));
  }, [all.data, kind, q]);
  const current = all.data?.find((e) => e.id === selected) ?? null;
  const select = (eid: string | null) => router.replace(eid ? `/p/${id}/codex?entry=${eid}` : `/p/${id}/codex`, { scroll: false });

  const create = useMutation({
    mutationFn: () => bookApi.createCodex(id, { kind: kind || "character", name: q.trim() || "New entry" }),
    onSuccess: (e) => { void qc.invalidateQueries({ queryKey: bk.codexAll(id) }); setQ(""); select(e.id); },
    onError: (e) => toast(String(e), "error"),
  });

  return (
    <Page wide>
      <PageHeader eyebrow="Story bible" title="Codex" description="The people, places and things in the book, and the facts the agents hold them to."
        actions={<Button onClick={() => create.mutate()} disabled={create.isPending}><Plus className="h-4 w-4" strokeWidth={1.75} /> New entry</Button>} />

      <ProposalsStrip id={id} />

      <div role="tablist" className="mt-8 flex flex-wrap gap-1 border-b border-rule">
        {TABS.map((t) => (
          <button key={t.kind} role="tab" type="button" aria-selected={kind === t.kind} onClick={() => setKind(t.kind)}
            className={clsx("-mb-px border-b-2 px-3 pb-2.5 pt-1 text-[14px] font-semibold transition-colors",
              kind === t.kind ? "border-ink text-ink" : "border-transparent text-body hover:text-ink")}>
            {t.label}
            <span className="ml-1.5 text-[12px] font-normal text-muted">
              {(all.data ?? []).filter((e) => !t.kind || e.kind === t.kind).length}
            </span>
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-10 lg:grid-cols-[320px_1fr]">
        <div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" strokeWidth={1.75} />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search names and aliases" className="pl-9" />
          </div>
          {all.isLoading && <div className="mt-4 space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>}
          <ul className="mt-3">
            {entries.map((e) => (
              <li key={e.id}>
                <button type="button" onClick={() => select(e.id)}
                  className={clsx("w-full rounded-[10px] px-3 py-2.5 text-left transition-colors",
                    e.id === selected ? "bg-sheet" : "hover:bg-sheet")}>
                  <span className="block text-[15px] font-semibold text-ink">{e.name}</span>
                  <span className="block truncate text-[12px] text-body">{kindLabel(e.kind)}{e.role && ` · ${e.role}`}{e.summary && ` · ${e.summary}`}</span>
                </button>
              </li>
            ))}
          </ul>
          {all.data && entries.length === 0 && <p className="mt-4 px-3 text-[13px] text-body">Nothing here yet.</p>}
        </div>

        <div className="min-w-0">
          {current
            ? <EntryEditor key={current.id + current.updated_at} id={id} entry={current} all={all.data ?? []} onDeleted={() => select(null)} />
            : <EmptyState title="Pick an entry" body="Select something on the left, or create a new entry for this tab." />}
        </div>
      </div>
    </Page>
  );
}

type FactRow = { k: string; v: string };

function EntryEditor({ id, entry, all, onDeleted }: { id: string; entry: CodexEntry; all: CodexEntry[]; onDeleted: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(entry.name);
  const [kind, setKind] = useState(entry.kind);
  const [role, setRole] = useState(entry.role);
  const [aliases, setAliases] = useState(entry.aliases.join(", "));
  const [summary, setSummary] = useState(entry.summary);
  const [notes, setNotes] = useState(entry.notes);
  const [facts, setFacts] = useState<FactRow[]>(Object.entries(entry.facts ?? {}).map(([k, v]) => ({ k, v: String(v) })));
  const [dirty, setDirty] = useState(false);
  const touch = <T,>(set: (v: T) => void) => (v: T) => { set(v); setDirty(true); };

  const invalidate = () => qc.invalidateQueries({ queryKey: bk.codexAll(id) });
  const save = useMutation({
    mutationFn: () => bookApi.updateCodex(id, entry.id, {
      name: name.trim() || entry.name, kind, role, summary, notes,
      aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
      facts: Object.fromEntries(facts.filter((f) => f.k.trim()).map((f) => [f.k.trim(), f.v])),
    }),
    onSuccess: () => { setDirty(false); void invalidate(); toast("Saved", "success"); },
    onError: (e) => toast(String(e), "error"),
  });
  const remove = useMutation({
    mutationFn: () => bookApi.deleteCodex(id, entry.id),
    onSuccess: () => { void invalidate(); onDeleted(); },
    onError: (e) => toast(String(e), "error"),
  });

  return (
    <div className="max-w-2xl">
      <div className="flex items-start justify-between gap-4">
        <input aria-label="Name" value={name} onChange={(e) => touch(setName)(e.target.value)}
          className="w-full bg-transparent font-display text-[36px] font-bold leading-tight tracking-[-0.03em] text-ink outline-none" />
        <Button variant="ghost" size="sm" aria-label="Delete entry" onClick={() => { if (confirm(`Delete ${entry.name}?`)) remove.mutate(); }}>
          <Trash2 className="h-4 w-4" strokeWidth={1.75} />
        </Button>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Field label="Kind">
          <Select aria-label="Kind" value={kind} onChange={(v) => touch(setKind)(v)} className="w-full"
            options={TABS.slice(1).map((t) => ({ value: t.kind, label: kindLabel(t.kind) }))} />
        </Field>
        <Field label="Role"><Input value={role} onChange={(e) => touch(setRole)(e.target.value)} placeholder="protagonist, minor…" /></Field>
        <Field label="Aliases" hint="comma separated"><Input value={aliases} onChange={(e) => touch(setAliases)(e.target.value)} /></Field>
      </div>

      <div className="mt-6"><Field label="Summary"><Textarea value={summary} onChange={(e) => touch(setSummary)(e.target.value)} /></Field></div>

      <section className="mt-8">
        <p className="mb-1 text-[12px] font-semibold text-ink">Facts</p>
        <p className="mb-3 text-[13px] text-body">Continuity checks read these. A <em>status</em> of dead or lost plus a <em>died_chapter</em> or <em>lost_chapter</em> flags later appearances.</p>
        <div className="space-y-2">
          {facts.map((f, i) => (
            <div key={i} className="grid grid-cols-[180px_1fr_auto] items-center gap-2">
              <Input aria-label="Fact" value={f.k} placeholder="status" onChange={(e) => touch(setFacts)(facts.map((x, j) => (j === i ? { ...x, k: e.target.value } : x)))} />
              <Input aria-label="Value" value={f.v} placeholder="alive" onChange={(e) => touch(setFacts)(facts.map((x, j) => (j === i ? { ...x, v: e.target.value } : x)))} />
              <button type="button" aria-label="Remove fact" onClick={() => touch(setFacts)(facts.filter((_, j) => j !== i))}
                className="rounded-[8px] p-2 text-muted hover:bg-sheet hover:text-ink"><X className="h-4 w-4" strokeWidth={1.75} /></button>
            </div>
          ))}
        </div>
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => touch(setFacts)([...facts, { k: "", v: "" }])}>
          <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add fact
        </Button>
      </section>

      <div className="mt-8"><Field label="Notes"><Textarea value={notes} onChange={(e) => touch(setNotes)(e.target.value)} /></Field></div>

      <div className="sticky bottom-0 mt-6 flex items-center gap-3 bg-paper py-4">
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>Save changes</Button>
        {dirty && <span className="text-[13px] text-muted">Unsaved changes</span>}
      </div>

      <Links id={id} entry={entry} all={all} />
    </div>
  );
}

function Links({ id, entry, all }: { id: string; entry: CodexEntry; all: CodexEntry[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const links = useQuery({ queryKey: bk.links(id), queryFn: () => bookApi.links(id) });
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("");
  const byId = Object.fromEntries(all.map((e) => [e.id, e]));
  const mine = (links.data ?? []).filter((l) => l.source_id === entry.id || l.target_id === entry.id);
  const add = useMutation({
    mutationFn: () => bookApi.createLink(id, { source_id: entry.id, target_id: target, label: label.trim() }),
    onSuccess: () => { setLabel(""); setTarget(""); void qc.invalidateQueries({ queryKey: bk.links(id) }); },
    onError: (e) => toast(String(e), "error"),
  });
  const del = useMutation({
    mutationFn: (linkId: string) => bookApi.deleteLink(id, linkId),
    onSuccess: () => qc.invalidateQueries({ queryKey: bk.links(id) }),
  });
  return (
    <section className="mt-6 border-t border-rule pt-6 pb-16">
      <p className="mb-3 text-[12px] font-semibold text-ink">Links</p>
      <ul>
        {mine.map((l) => {
          const outgoing = l.source_id === entry.id;
          const other = byId[outgoing ? l.target_id : l.source_id];
          return (
            <li key={l.id} className="flex items-center justify-between border-b border-rule py-2 text-[14px]">
              <span>
                {outgoing ? <>{entry.name} <span className="text-body">{l.label || "linked to"}</span> {other?.name}</>
                  : <>{other?.name} <span className="text-body">{l.label || "linked to"}</span> {entry.name}</>}
              </span>
              <button type="button" aria-label="Remove link" onClick={() => del.mutate(l.id)} className="rounded-[8px] p-1.5 text-muted hover:bg-sheet hover:text-ink">
                <X className="h-4 w-4" strokeWidth={1.75} />
              </button>
            </li>
          );
        })}
      </ul>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (target) add.mutate(); }}>
        <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="sister, owns, located in…" className="w-48" />
        <Select aria-label="Link to" value={target || null} onChange={(v) => setTarget(v)} className="min-w-0 flex-1" placeholder="Choose an entry…"
          options={all.filter((e) => e.id !== entry.id).map((e) => ({ value: e.id, label: e.name }))} />
        <Button type="submit" variant="secondary" disabled={!target || add.isPending}>Link</Button>
      </form>
    </section>
  );
}
