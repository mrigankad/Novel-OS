"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Pencil, Pin, Plus, Search, Trash2 } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { EmptyState, Page, PageHeader, SectionLabel, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { agentKeys, agentsApi, MEMORY_KINDS, type Agent, type Memory, type MemoryKind } from "@/lib/api/agents";
import { AgentGlyph } from "./agent-icon";

const KIND_LABEL: Record<MemoryKind, string> = {
  fact: "Facts", decision: "Your decisions", preference: "Your preferences", style: "Style notes",
  summary: "Chapter summaries", research: "Research", episode: "What happened in runs",
};


function MemoryRow({ m, agent, onPatch, onDelete }: {
  m: Memory; agent?: Agent; onPatch: (b: Partial<Memory>) => void; onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.content);
  return (
    <li className="group flex gap-4 border-b border-rule py-3 last:border-0">
      <div className="min-w-0 flex-1">
        {editing ? (
          <div className="flex flex-col gap-2">
            <Textarea value={text} onChange={(e) => setText(e.target.value)} autoFocus />
            <div className="flex gap-2">
              <Button size="sm" onClick={() => { onPatch({ content: text }); setEditing(false); }}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => { setText(m.content); setEditing(false); }}>Cancel</Button>
            </div>
          </div>
        ) : (
          <p className="text-[14px] leading-relaxed text-ink">{m.content}</p>
        )}
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[12px] text-muted">
          <span>{agent ? agent.name : "Shared"}</span>
          {m.chapter != null && <span>· Ch {m.chapter}</span>}
          {m.source && <span>· {m.source.split(":")[0]}</span>}
          <span>· recalled {m.recall_count}×</span>
        </p>
      </div>
      <div className="flex shrink-0 items-start gap-1">
        <label className="flex items-center gap-2 pt-1 text-[11px] text-muted" title="Importance">
          <input type="range" min={0} max={1} step={0.1} defaultValue={m.importance}
            onPointerUp={(e) => onPatch({ importance: Number((e.target as HTMLInputElement).value) })}
            onKeyUp={(e) => onPatch({ importance: Number((e.target as HTMLInputElement).value) })}
            className="w-20 accent-gall" aria-label="Importance" />
        </label>
        <Button size="sm" variant="ghost" aria-label={m.pinned ? "Unpin" : "Pin"} onClick={() => onPatch({ pinned: !m.pinned })}
          className={clsx("px-2", m.pinned && "text-gall")}>
          <Pin className="h-4 w-4" strokeWidth={1.75} fill={m.pinned ? "currentColor" : "none"} />
        </Button>
        <Button size="sm" variant="ghost" aria-label="Edit" className="px-2" onClick={() => setEditing(true)}>
          <Pencil className="h-4 w-4" strokeWidth={1.75} />
        </Button>
        <Button size="sm" variant="ghost" aria-label="Delete" className="px-2 hover:text-fail" onClick={onDelete}>
          <Trash2 className="h-4 w-4" strokeWidth={1.75} />
        </Button>
      </div>
    </li>
  );
}

export default function MemoryScreen({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<{ kind: MemoryKind; content: string; agent_id: string; chapter: string }>(
    { kind: "fact", content: "", agent_id: "", chapter: "" });
  const dq = useDeferredValue(q);
  const filters = { q: dq, agent_id: agentFilter || undefined, kind: kindFilter || undefined };

  const agents = useQuery({ queryKey: agentKeys.agents(projectId), queryFn: () => agentsApi.list(projectId) });
  const memories = useQuery({
    queryKey: agentKeys.memory(projectId, filters),
    queryFn: () => agentsApi.memory(projectId, filters),
    placeholderData: (prev) => prev,
  });
  const byId = new Map((agents.data ?? []).map((a) => [a.id, a]));
  const invalidate = () => qc.invalidateQueries({ queryKey: ["p", projectId, "memory"] });

  const patch = useMutation({
    mutationFn: ({ mid, body }: { mid: string; body: Partial<Memory> }) => agentsApi.updateMemory(projectId, mid, body),
    onSuccess: invalidate,
    onError: (e: Error) => toast(e.message, "error"),
  });
  const remove = useMutation({
    mutationFn: (mid: string) => agentsApi.removeMemory(projectId, mid),
    onSuccess: () => { void invalidate(); toast("Forgotten"); },
  });
  const add = useMutation({
    mutationFn: () => agentsApi.addMemory(projectId, {
      kind: draft.kind, content: draft.content, agent_id: draft.agent_id || null,
      chapter: draft.chapter ? Number(draft.chapter) : null, importance: 0.7,
    }),
    onSuccess: () => { void invalidate(); setAdding(false); setDraft({ kind: "fact", content: "", agent_id: "", chapter: "" }); toast("Remembered", "success"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const rows = memories.data ?? [];
  const groups = MEMORY_KINDS.map((k) => [k, rows.filter((m) => m.kind === k)] as const).filter(([, xs]) => xs.length);

  return (
    <Page>
      <PageHeader
        eyebrow="Memory"
        title="What your agents remember"
        description="Facts, rulings and preferences your agents recall before every run. Shared memories reach the whole cast; the rest belong to one agent. Pin what must never be forgotten."
        actions={<Button onClick={() => setAdding((v) => !v)}><Plus className="h-4 w-4" strokeWidth={1.75} /> Add memory</Button>}
      />

      {adding && (
        <form className="mt-8 grid gap-4 rounded-[16px] bg-sheet p-5 sm:grid-cols-[160px_1fr_160px_100px]"
          onSubmit={(e) => { e.preventDefault(); if (draft.content.trim()) add.mutate(); }}>
          <Field label="Kind">
            <Select<MemoryKind> aria-label="Kind" className="w-full" value={draft.kind} onChange={(v) => setDraft({ ...draft, kind: v })}
              options={MEMORY_KINDS.map((k) => ({ value: k, label: k }))} />
          </Field>
          <Field label="What to remember">
            <Input value={draft.content} autoFocus placeholder="Iris never swears." onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
          </Field>
          <Field label="Who">
            <Select aria-label="Who" className="w-full" value={draft.agent_id} onChange={(v) => setDraft({ ...draft, agent_id: v })}
              options={[{ value: "", label: "Shared" }, ...(agents.data ?? []).map((a) => ({ value: a.id, label: a.name }))]} />
          </Field>
          <Field label="Chapter">
            <Input type="number" min={1} value={draft.chapter} onChange={(e) => setDraft({ ...draft, chapter: e.target.value })} />
          </Field>
          <div className="flex gap-2 sm:col-span-4">
            <Button type="submit" disabled={!draft.content.trim() || add.isPending}>Save memory</Button>
            <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </form>
      )}

      <div className="mt-8 flex flex-wrap gap-2">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" strokeWidth={1.75} />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search memories" className="pl-9" />
        </div>
        <Select className="w-44" value={agentFilter} onChange={(v) => setAgentFilter(v)} aria-label="Agent"
          options={[{ value: "", label: "Every agent" }, { value: "shared", label: "Shared only" }, ...(agents.data ?? []).map((a) => ({ value: a.id, label: a.name }))]} />
        <Select className="w-44" value={kindFilter} onChange={(v) => setKindFilter(v)} aria-label="Kind"
          options={[{ value: "", label: "Every kind" }, ...MEMORY_KINDS.map((k) => ({ value: k as string, label: KIND_LABEL[k] }))]} />
      </div>

      {memories.isLoading ? <Skeleton className="mt-8 h-64" /> : groups.length === 0 ? (
        <div className="mt-8">
          <EmptyState title={q ? "Nothing matches" : "Nothing remembered yet"}
            body={q ? "Try another word." : "Agents add facts as they draft. Click “Remember this” on a message in the room to keep a rule."} />
        </div>
      ) : groups.map(([kind, xs]) => (
        <section key={kind}>
          <SectionLabel>{KIND_LABEL[kind]} · {xs.length}</SectionLabel>
          <ul>
            {xs.map((m) => (
              <MemoryRow key={`${m.id}-${m.content}`} m={m} agent={m.agent_id ? byId.get(m.agent_id) : undefined}
                onPatch={(body) => patch.mutate({ mid: m.id, body })} onDelete={() => remove.mutate(m.id)} />
            ))}
          </ul>
        </section>
      ))}
      {agents.data && agents.data.length > 0 && (
        <p className="mt-10 flex items-center gap-2 text-[12px] text-muted">
          <AgentGlyph role="guardian" size="sm" /> Agents recall up to 12 memories per run, ranked by relevance, importance, recency and chapter.
        </p>
      )}
    </Page>
  );
}
