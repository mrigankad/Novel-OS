"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { AlertTriangle, CheckCircle2, Circle, Loader2, Play, Square, XCircle } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { agentKeys, agentsApi, type Stage, type Task } from "@/lib/api/agents";
import { AgentGlyph } from "./agent-icon";

const STAGE_LABEL: Record<string, string> = { plan: "Plan", draft: "Draft", edit: "Edit", check: "Check" };

function StageIcon({ status }: { status: Stage["status"] }) {
  const cls = "h-4 w-4 shrink-0";
  if (status === "running" || status === "queued") return <Loader2 className={clsx(cls, "animate-spin text-gall")} strokeWidth={1.75} />;
  if (status === "done") return <CheckCircle2 className={clsx(cls, "text-pass")} strokeWidth={1.75} />;
  if (status === "failed") return <XCircle className={clsx(cls, "text-fail")} strokeWidth={1.75} />;
  return <Circle className={clsx(cls, "text-rule-strong")} strokeWidth={1.75} />;
}

// Owner: agents area. Mounted by the chapter writing screen (/p/[id]/write/[n]).
export default function ChapterAgentPanel({ projectId, chapter }: { projectId: string; chapter: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const status = useQuery({
    queryKey: agentKeys.status(projectId, chapter),
    queryFn: () => agentsApi.status(projectId, chapter),
    retry: false,
  });
  const agents = useQuery({ queryKey: agentKeys.agents(projectId), queryFn: () => agentsApi.list(projectId) });
  const byId = new Map((agents.data ?? []).map((a) => [a.id, a]));

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["p", projectId, "run"] });
    void qc.invalidateQueries({ queryKey: ["p", projectId, "message"] });
  };
  const task = useMutation({
    mutationFn: (t: Task) => agentsApi.chapterTask(projectId, chapter, t),
    onSuccess: refresh,
    onError: (e: Error) => toast(e.message, "error"),
  });
  const pipeline = useMutation({
    mutationFn: () => agentsApi.pipeline(projectId, chapter),
    onSuccess: () => { refresh(); toast("Pipeline started"); },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const stop = useMutation({
    mutationFn: (rid: string) => agentsApi.cancel(projectId, rid),
    onSuccess: (r) => { refresh(); toast(r.status === "cancelled" ? "Stopped" : "Stopping…"); },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const act = useMutation({
    mutationFn: ({ mid, action }: { mid: string; action: string }) =>
      agentsApi.act(projectId, status.data!.thread_id, mid, action),
    onSuccess: (r) => { refresh(); if (r.note) toast(r.note, "success"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const s = status.data;
  const busy = s?.stages.some((x) => x.status === "running" || x.status === "queued");
  const objection = s?.objection && s.objection.actions.length > 0 ? s.objection : null;

  return (
    <aside className="flex w-[340px] shrink-0 flex-col gap-7 overflow-y-auto border-l border-rule p-5">
      <div className="flex items-center justify-between">
        <p className="font-display text-[18px] font-bold tracking-[-0.02em] text-ink">Agents</p>
        <Link href={`/p/${projectId}/room?chapter=${chapter}`} className="text-[12px] font-semibold text-gall hover:underline">
          Writers&apos; room
        </Link>
      </div>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <p className="label">Pipeline</p>
          <Button size="sm" variant="ai" onClick={() => pipeline.mutate()} disabled={busy || pipeline.isPending}>
            <Play className="h-3.5 w-3.5" strokeWidth={1.75} /> Run all
          </Button>
        </div>
        {status.isLoading ? <Skeleton className="h-40" /> : status.isError ? (
          <p className="text-[13px] text-body">This chapter isn&apos;t saved yet.</p>
        ) : (
          <ol className="flex flex-col">
            {s?.stages.map((st, i) => {
              const a = st.agent_id ? byId.get(st.agent_id) : undefined;
              return (
                <li key={st.task} className="flex items-center gap-3 py-2">
                  <AgentGlyph role={st.role} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold text-ink">
                      {i + 1}. {STAGE_LABEL[st.task]} <span className="font-normal text-body">· {st.agent_name || "No agent"}</span>
                    </p>
                    <p className="truncate text-[11px] text-muted">{a?.model_line ?? ""}</p>
                    {st.status === "running" && <div className="mt-1 h-1 overflow-hidden rounded-full bg-sheet"><div className="h-full w-1/2 animate-pulse rounded-full bg-gall" /></div>}
                    {st.error && <p className="truncate text-[11px] text-fail" title={st.error}>{st.error}</p>}
                  </div>
                  {(st.status === "running" || st.status === "queued") && st.run_id && (
                    <Button size="sm" variant="ghost" className="h-6 px-2 text-[12px]" disabled={stop.isPending}
                      aria-label={`Stop ${STAGE_LABEL[st.task]}`} onClick={() => stop.mutate(st.run_id!)}>
                      <Square className="h-3 w-3" strokeWidth={1.75} /> Stop
                    </Button>
                  )}
                  <StageIcon status={st.status} />
                </li>
              );
            })}
          </ol>
        )}
        <div className="mt-3 grid grid-cols-4 gap-1.5">
          {(["plan", "draft", "edit", "check"] as Task[]).map((t) => (
            <Button key={t} size="sm" variant="secondary" disabled={task.isPending || busy || status.isError}
              onClick={() => task.mutate(t)} className="px-0">
              {STAGE_LABEL[t]}
            </Button>
          ))}
        </div>
      </section>

      {objection && (
        <section className="rounded-[14px] border border-[color-mix(in_srgb,var(--color-fail)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-fail)_5%,transparent)] p-4">
          <p className="flex items-center gap-1.5 text-[12px] font-semibold text-fail">
            <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.75} /> Guardian objection
          </p>
          <p className="mt-2 line-clamp-6 whitespace-pre-wrap text-[13px] leading-relaxed text-ink">{objection.body}</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="primary" disabled={act.isPending}
              onClick={() => act.mutate({ mid: objection.id, action: "fix" })}>Fix in text</Button>
            <Button size="sm" variant="ghost" disabled={act.isPending}
              onClick={() => act.mutate({ mid: objection.id, action: "intentional" })}>This is intentional</Button>
          </div>
        </section>
      )}

      <section>
        <p className="label mb-2">In context for this run</p>
        {s?.context.run_id ? (
          <dl className="grid grid-cols-2 gap-y-2 text-[13px]">
            <dt className="text-body">Memories recalled</dt>
            <dd className="text-right font-semibold text-ink">{s.context.memories}</dd>
            <dt className="text-body">Tokens in context</dt>
            <dd className="text-right font-semibold text-ink">{s.context.tokens.toLocaleString()}</dd>
            {s.context.codex.length > 0 && (
              <>
                <dt className="text-body">Codex</dt>
                <dd className="truncate text-right text-ink" title={s.context.codex.join(", ")}>{s.context.codex.join(", ")}</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="text-[13px] text-body">Nothing yet. Run a step to see what the agent was given.</p>
        )}
        <Link href={`/p/${projectId}/memory`} className="mt-3 inline-block text-[12px] font-semibold text-gall hover:underline">
          What your agents remember
        </Link>
      </section>
    </aside>
  );
}
