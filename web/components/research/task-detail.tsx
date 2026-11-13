"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookPlus, Check, ExternalLink, RotateCcw, Square, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, SectionLabel, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { isRunning, researchApi, researchKeys, type ResearchSource } from "@/lib/api/research";
import { StatusDot } from "./task-list";

function Reliability({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.7 ? "bg-pass" : value >= 0.4 ? "bg-warn" : "bg-fail";
  return (
    <span className="flex items-center gap-2 text-[11px] text-muted" title={`Reliability ${pct}%`}>
      <span className="relative h-1 w-16 overflow-hidden rounded-full bg-rule">
        <span className={`absolute inset-y-0 left-0 ${tone}`} style={{ width: `${pct}%` }} />
      </span>
      {pct}%
    </span>
  );
}

function SourceRow({ projectId, source, n, question }: { projectId: string; source: ResearchSource; n: number; question: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const file = useMutation({
    mutationFn: () => researchApi.file(projectId, source.id, { name: `Research: ${question.slice(0, 80)}` }),
    onSuccess: () => {
      toast("Filed to the Codex", "success");
      void qc.invalidateQueries({ queryKey: researchKeys.all(projectId) });
      void qc.invalidateQueries({ queryKey: ["p", projectId, "codex"] });
    },
    onError: (e) => toast(String(e), "error"),
  });
  return (
    <li className="py-5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[12px] font-semibold text-muted">[{n}]</span>
        <p className="min-w-0 flex-1 text-[15px] font-semibold text-ink">{source.title || source.domain}</p>
        <Reliability value={source.reliability} />
      </div>
      <p className="mt-0.5 pl-7 text-[12px] text-muted">{source.domain}</p>
      {source.note && <p className="mt-2 pl-7 text-[14px] text-body">{source.note}</p>}
      {source.excerpt && (
        <blockquote className="mt-2 ml-7 border-l-2 border-rule-strong pl-4 font-prose text-[16px] italic leading-relaxed text-[#2a2933]">
          &ldquo;{source.excerpt}&rdquo;
        </blockquote>
      )}
      <div className="mt-3 flex gap-2 pl-7">
        {source.filed_to_codex_id ? (
          <Badge tone="pass"><Check className="h-3 w-3" strokeWidth={1.75} /> In the Codex</Badge>
        ) : (
          <Button size="sm" variant="secondary" disabled={file.isPending} onClick={() => file.mutate()}>
            <BookPlus className="h-3.5 w-3.5" strokeWidth={1.75} /> File to Codex
          </Button>
        )}
        <a href={source.url} target="_blank" rel="noreferrer noopener"
          className="inline-flex h-8 items-center gap-2 rounded-[10px] px-3 text-[13px] font-semibold text-body hover:bg-sheet hover:text-ink">
          <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.75} /> Open
        </a>
      </div>
    </li>
  );
}

export function TaskDetail({ projectId, taskId, onDeleted }: { projectId: string; taskId: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: task, isLoading } = useQuery({
    queryKey: researchKeys.task(projectId, taskId),
    queryFn: () => researchApi.get(projectId, taskId),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: researchKeys.all(projectId) });
  const cancel = useMutation({ mutationFn: () => researchApi.cancel(projectId, taskId), onSuccess: refresh });
  const retry = useMutation({ mutationFn: () => researchApi.retry(projectId, taskId), onSuccess: refresh,
    onError: (e) => toast(String(e), "error") });
  const remove = useMutation({
    mutationFn: () => researchApi.remove(projectId, taskId),
    onSuccess: () => { void refresh(); onDeleted(); },
  });

  if (isLoading || !task) return <div className="space-y-3"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-40" /></div>;
  const running = isRunning(task.status);

  return (
    <article>
      <div className="flex items-start gap-3">
        <span className="mt-3"><StatusDot status={task.status} /></span>
        <h2 className="flex-1 font-display text-[28px] font-bold leading-tight tracking-[-0.02em] text-ink">{task.question}</h2>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 pl-5">
        <p className={`flex-1 text-[13px] ${running ? "text-gall" : "text-muted"}`}>
          {task.progress}{task.chapter != null && ` · Chapter ${task.chapter}`}
        </p>
        {running ? (
          <Button size="sm" variant="ghost" onClick={() => cancel.mutate()}><Square className="h-3.5 w-3.5" strokeWidth={1.75} /> Stop</Button>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => retry.mutate()} disabled={retry.isPending}>
            <RotateCcw className="h-3.5 w-3.5" strokeWidth={1.75} /> Run again
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => remove.mutate()} aria-label="Delete task">
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
        </Button>
      </div>

      {task.summary ? (
        <div className="prose-book mt-8 whitespace-pre-line">{task.summary}</div>
      ) : running ? (
        <div className="mt-8 space-y-2"><Skeleton className="h-4" /><Skeleton className="h-4 w-5/6" /><Skeleton className="h-4 w-4/6" /></div>
      ) : null}

      <SectionLabel>Sources · {task.sources.length}</SectionLabel>
      {task.sources.length === 0 ? (
        <EmptyState
          title={running ? "Reading the web" : "No sources kept"}
          body={running ? "Findings appear here once the browsers finish reading." : "Nothing citable turned up. Try a narrower question."}
        />
      ) : (
        <ol className="divide-y divide-rule">
          {task.sources.map((s, i) => <SourceRow key={s.id} projectId={projectId} source={s} n={i + 1} question={task.question} />)}
        </ol>
      )}
    </article>
  );
}
