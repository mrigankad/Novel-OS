"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ChevronLeft, ChevronRight, Globe, Pencil, Play, Plus, Square, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Drawer } from "@/components/ui/drawer";
import { Select } from "@/components/ui/select";
import { Badge, EmptyState, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { agentKeys, agentsApi, type Agent, type Autonomy, type Message, type Run } from "@/lib/api/agents";
import { AgentGlyph } from "./agent-icon";
import { AgentSheet } from "./agent-sheet";
import { Assignments } from "./assignments";
import { Composer } from "./composer";
import { RoomMessage } from "./room-messages";
import { BrandIcon } from "@/components/brand-icon";

const STATUS_TONE = { writing: "ai", idle: "neutral", objection: "fail" } as const;

function CastCard({ a, selected, onOpen, run, onStop }: {
  a: Agent; selected: boolean; onOpen: () => void; run?: Run; onStop: (rid: string) => void;
}) {
  return (
    <li className={clsx(
      "group relative rounded-[14px] border p-3 transition-colors hover:border-rule-strong",
      selected ? "border-gall ring-1 ring-gall" : "border-rule",
      !a.enabled && "opacity-50",
    )}>
      <button type="button" onClick={onOpen} aria-label={`Edit ${a.name}`} className="absolute inset-0 rounded-[14px]" />
      <div className="pointer-events-none relative flex items-start gap-3">
        <AgentGlyph role={a.role} tone={a.status === "objection" ? "fail" : "soft"} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-[14px] font-semibold text-ink">{a.name}</p>
            <Badge tone={STATUS_TONE[a.status]} dot>{a.status}</Badge>
          </div>
          <p className="flex items-center gap-1.5 truncate text-[12px] text-muted" title={a.model_line}>
            {a.route_provider && <BrandIcon id={a.route_provider} size="xs" className="opacity-80" />}
            <span className="truncate">{a.model_line}</span>
          </p>
        </div>
      </div>
      {a.chapters.length > 0 && (
        <div className="pointer-events-none relative mt-2 flex flex-wrap gap-1 pl-12">
          {a.chapters.map((n) => (
            <span key={n} className="rounded-full bg-sheet px-2 py-0.5 text-[11px] font-semibold text-body">Ch {n}</span>
          ))}
        </div>
      )}
      <div className="relative mt-2 flex items-center gap-1 pl-12">
        {run && (
          <button type="button" onClick={() => onStop(run.id)}
            className="inline-flex h-6 items-center gap-1 rounded-full border border-rule-strong px-2 text-[11px] font-semibold text-ink hover:border-ink">
            <Square className="h-2.5 w-2.5" strokeWidth={1.75} /> Stop {run.task}
          </button>
        )}
        <button type="button" onClick={onOpen}
          className="inline-flex h-6 items-center gap-1 rounded-full px-2 text-[11px] font-semibold text-body opacity-0 transition-opacity hover:text-ink focus:opacity-100 group-hover:opacity-100">
          <Pencil className="h-3 w-3" strokeWidth={1.75} /> Edit
        </button>
      </div>
    </li>
  );
}

function Segmented({ value, onChange }: { value: Autonomy; onChange: (v: Autonomy) => void }) {
  const opts: [Autonomy, string][] = [["ask", "Ask before acting"], ["autopilot", "Autopilot"]];
  return (
    <div className="inline-flex rounded-[10px] bg-sheet p-0.5" role="radiogroup" aria-label="Autonomy">
      {opts.map(([v, label]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={clsx("h-8 rounded-[8px] px-3 text-[12px] font-semibold transition-colors",
            value === v ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.08)]" : "text-body hover:text-ink")}>
          {label}
        </button>
      ))}
    </div>
  );
}

export default function Room() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();

  const agents = useQuery({ queryKey: agentKeys.agents(id), queryFn: () => agentsApi.list(id) });
  const chapters = useQuery({ queryKey: agentKeys.chapters(id), queryFn: () => agentsApi.chapters(id) });
  const research = useQuery({ queryKey: agentKeys.research(id), queryFn: () => agentsApi.research(id), retry: false });

  const list = chapters.data ?? [];
  const requested = Number(search.get("chapter"));
  const chapter = list.find((c) => c.number === requested)?.number ?? list[0]?.number;
  const idx = list.findIndex((c) => c.number === chapter);
  const go = (n: number) => router.replace(`/p/${id}/room?chapter=${n}`);
  const thread = useQuery({
    queryKey: agentKeys.thread(id, chapter ?? -1),
    queryFn: () => agentsApi.chapterThread(id, chapter!),
    enabled: chapter !== undefined,
  });
  const tid = thread.data?.id;
  const messages = useQuery({
    queryKey: agentKeys.messages(id, tid ?? "none"),
    queryFn: () => agentsApi.messages(id, tid!),
    enabled: !!tid,
  });

  const byId = useMemo(() => new Map((agents.data ?? []).map((a) => [a.id, a])), [agents.data]);
  const current = list.find((c) => c.number === chapter);
  const cast = agents.data ?? [];
  const autonomy: Autonomy = cast.length && cast.every((a) => a.autonomy === "autopilot") ? "autopilot" : "ask";

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["p", id, "message"] });
    void qc.invalidateQueries({ queryKey: ["p", id, "agent"] });
    void qc.invalidateQueries({ queryKey: ["p", id, "run"] });
  };
  const send = useMutation({
    mutationFn: (body: string) => agentsApi.send(id, tid!, body),
    onSuccess: invalidate,
    onError: (e: Error) => toast(e.message, "error"),
  });
  const act = useMutation({
    mutationFn: ({ m, action }: { m: Message; action: string }) => agentsApi.act(id, m.thread_id, m.id, action),
    onSuccess: (r) => {
      invalidate();
      void qc.invalidateQueries({ queryKey: ["p", id, "memory"] });
      if (r.note) toast(r.note, "success");
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const setAutonomy = useMutation({
    mutationFn: (v: Autonomy) => agentsApi.setAutonomy(id, v),
    onSuccess: (data) => qc.setQueryData(agentKeys.agents(id), data),
  });
  const pipeline = useMutation({
    mutationFn: () => agentsApi.pipeline(id, chapter!),
    onSuccess: invalidate,
    onError: (e: Error) => toast(e.message, "error"),
  });

  const runs = useQuery({ queryKey: agentKeys.activeRuns(id), queryFn: () => agentsApi.runs(id) });
  const active = useMemo(() => (runs.data ?? []).filter((r) => r.status === "queued" || r.status === "running"), [runs.data]);
  const activeByAgent = useMemo(() => {
    const m = new Map<string, Run>();
    for (const r of active) if (r.agent_id && !m.has(r.agent_id)) m.set(r.agent_id, r);
    return m;
  }, [active]);
  const activeIds = useMemo(() => new Set(active.map((r) => r.id)), [active]);
  const stop = useMutation({
    mutationFn: (rid: string) => agentsApi.cancel(id, rid),
    onSuccess: (r) => { invalidate(); toast(r.status === "cancelled" ? "Stopped" : "Stopping…"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const view = search.get("view") === "assignments" ? "assignments" : "room";
  const setView = (v: "room" | "assignments") => {
    const qs = new URLSearchParams(search.toString());
    if (v === "room") qs.delete("view"); else qs.set("view", v);
    router.replace(`/p/${id}/room?${qs.toString()}`);
  };
  const [sheet, setSheet] = useState<{ open: boolean; agentId?: string }>({ open: false });
  const editing = sheet.agentId ? byId.get(sheet.agentId) : undefined;

  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [messages.data?.length]);

  const castPanel = (
    <>
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="eyebrow mb-1">Agents</p>
            <h2 className="font-display text-[24px] font-bold tracking-[-0.02em] text-ink">The cast</h2>
          </div>
          <Button size="sm" variant="secondary" onClick={() => setSheet({ open: true })}>
            <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> New agent
          </Button>
        </div>
        {agents.isLoading ? <Skeleton className="h-64" /> : (
          <ul className="flex flex-col gap-2">
            {cast.map((a) => (
              <CastCard key={a.id} a={a} selected={chapter !== undefined && (current?.assigned_agent_id === a.id)}
                onOpen={() => setSheet({ open: true, agentId: a.id })}
                run={activeByAgent.get(a.id)} onStop={(rid) => stop.mutate(rid)} />
            ))}
          </ul>
        )}
        <Link href="/settings/agents" className="text-[12px] font-semibold text-gall hover:underline">Agents and models</Link>
    </>
  );
  const [castOpen, setCastOpen] = useState(false);

  return (
    <div className="flex h-full min-h-0 lg:h-screen">
      {/* The cast: inline on wide screens, a drawer below lg */}
      <section className="hidden w-[300px] shrink-0 flex-col gap-4 overflow-y-auto border-r border-rule px-5 py-6 lg:flex">
        {castPanel}
      </section>
      <Drawer open={castOpen} onClose={() => setCastOpen(false)} side="left" label="The cast">
        <div className="flex flex-col gap-4 px-5 py-6">{castPanel}</div>
      </Drawer>

      {/* Writers' room */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-4 sm:px-8">
          <Button size="sm" variant="secondary" className="lg:hidden" onClick={() => setCastOpen(true)}>
            <Users className="h-3.5 w-3.5" strokeWidth={1.75} /> Cast
          </Button>
          <div className="inline-flex rounded-[10px] bg-sheet p-0.5" role="tablist" aria-label="View">
            {([["room", "Room"], ["assignments", "Assignments"]] as const).map(([v, label]) => (
              <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => setView(v)}
                className={clsx("h-8 rounded-[8px] px-3 text-[12px] font-semibold transition-colors",
                  view === v ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.08)]" : "text-body hover:text-ink")}>
                {label}
              </button>
            ))}
          </div>
          {view === "room" && <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" aria-label="Previous chapter" disabled={idx <= 0}
              onClick={() => go(list[idx - 1].number)}><ChevronLeft className="h-4 w-4" strokeWidth={1.75} /></Button>
            <Select<number>
              aria-label="Chapter"
              size="sm"
              value={chapter}
              onChange={(v) => go(v)}
              className="min-w-[12rem] max-w-[18rem]"
              options={list.map((c) => ({ value: c.number, label: `Chapter ${c.number}${c.title ? ` · ${c.title}` : ""}` }))}
            />
            <Button size="sm" variant="ghost" aria-label="Next chapter" disabled={idx < 0 || idx >= list.length - 1}
              onClick={() => go(list[idx + 1].number)}><ChevronRight className="h-4 w-4" strokeWidth={1.75} /></Button>
          </div>}
          <div className="flex items-center gap-2">
            <Segmented value={autonomy} onChange={(v) => setAutonomy.mutate(v)} />
            {view === "room" && (
              <Button size="sm" variant="ai" disabled={chapter === undefined || pipeline.isPending} onClick={() => pipeline.mutate()}>
                <Play className="h-3.5 w-3.5" strokeWidth={1.75} /> Run pipeline
              </Button>
            )}
          </div>
        </header>
        <div className="px-8 pt-6">
          <h1 className="font-display text-[32px] font-bold leading-tight tracking-[-0.03em] text-ink">
            {view === "assignments" ? "Who writes what" : <>Writers&apos; room{chapter !== undefined && <span className="text-muted"> · Chapter {chapter}</span>}</>}
          </h1>
        </div>
        {view === "assignments" ? (
          <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
            {chapters.isLoading || agents.isLoading ? <Skeleton className="h-40" /> : (
              <Assignments projectId={id} cast={cast} chapters={list} onOpenAgent={(a) => setSheet({ open: true, agentId: a.id })} />
            )}
          </div>
        ) : <>
        <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
          {chapters.isLoading ? <Skeleton className="h-40" /> : list.length === 0 ? (
            <EmptyState title="No chapters yet" body="Add a chapter in the manuscript, then bring the cast in here to plan and draft it." />
          ) : messages.data?.length === 0 ? (
            <EmptyState title="The room is quiet" body="Ask an agent something with @, or run the pipeline to plan, draft, edit and check this chapter." />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
              {messages.data?.map((m) => (
                <RoomMessage key={m.id} m={m} agents={byId} busy={act.isPending}
                  onAction={(msg, action) => act.mutate({ m: msg, action })}
                  onStop={(rid) => stop.mutate(rid)} runActive={!!m.run_id && activeIds.has(m.run_id)} />
              ))}
              <div ref={endRef} />
            </div>
          )}
        </div>
        <div className="border-t border-rule px-8 py-4">
          <div className="mx-auto max-w-3xl">
            <Composer agents={cast} disabled={!tid || send.isPending} onSend={(b) => send.mutate(b)} />
          </div>
        </div>
        </>}
      </section>

      <AgentSheet projectId={id} open={sheet.open} agent={editing} cast={cast} chapters={list}
        onClose={() => setSheet({ open: false })} />

      {/* Research swarm */}
      <section className="hidden w-[260px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-rule px-5 py-6 xl:flex">
        <p className="flex items-center gap-2 text-[14px] font-semibold text-ink">
          <Globe className="h-4 w-4 text-gall" strokeWidth={1.75} /> Research swarm
        </p>
        {research.isLoading ? <Skeleton className="h-24" /> : (research.data ?? []).length === 0 ? (
          <p className="text-[13px] leading-relaxed text-body">
            No research running. Ask <span className="font-semibold text-ink">@Researcher</span> in the room, or open the swarm.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {research.data!.slice(0, 8).map((r) => (
              <li key={r.id} className="text-[13px]">
                <p className="line-clamp-2 text-ink">{r.question ?? r.title ?? "Research task"}</p>
                {r.status && <p className="text-[11px] text-muted">{r.status}</p>}
              </li>
            ))}
          </ul>
        )}
        <Link href={`/p/${id}/research`} className="text-[12px] font-semibold text-gall hover:underline">Open research</Link>
      </section>
    </div>
  );
}
