"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Volume2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/page";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { audioApi, audioKeys, formatDuration, type AudioChapter } from "@/lib/api/audio";

const FINISHED = ["done", "failed", "cancelled"];

export function ChapterList({ projectId, canRender }: { projectId: string; canRender: boolean }) {
  const chapters = useQuery({ queryKey: audioKeys.chapters(projectId), queryFn: () => audioApi.chapters(projectId) });
  if (chapters.isLoading) return <p className="text-[14px] text-muted">Loading chapters…</p>;
  const rows = chapters.data ?? [];
  if (!rows.length) return <p className="text-[14px] text-muted">No chapters yet.</p>;
  return (
    <ol className="divide-y divide-rule border-y border-rule">
      {rows.map((c) => <ChapterRow key={c.number} projectId={projectId} chapter={c} canRender={canRender} />)}
    </ol>
  );
}

function ChapterRow({ projectId, chapter, canRender }: { projectId: string; chapter: AudioChapter; canRender: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [runId, setRunId] = useState<string | null>(null);
  const t = chapter.track;

  const run = useQuery({
    queryKey: ["p", projectId, "run", "audio", runId],
    queryFn: async () => {
      const d = await audioApi.run(projectId, runId!);
      if (FINISHED.includes(d.status)) {
        if (d.status === "done") toast(`Chapter ${chapter.number} rendered`, "success");
        else toast(d.error.replace(/^\w+Error: /, "") || "Rendering stopped", "error");
        setRunId(null);
        void qc.invalidateQueries({ queryKey: audioKeys.all(projectId) });
      }
      return d;
    },
    enabled: !!runId,
    refetchInterval: 1500,
  });

  const render = useMutation({
    mutationFn: (force: boolean) => audioApi.render(projectId, chapter.number, force),
    onSuccess: (r) => {
      if (r.run_id) setRunId(r.run_id);
      else {
        if (r.status === "skipped") toast("Unchanged since the last render. Already up to date.", "info");
        void qc.invalidateQueries({ queryKey: audioKeys.all(projectId) });
      }
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const busy = render.isPending || !!runId;
  const status = run.data?.status;
  return (
    <li className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="min-w-0">
        <p className="truncate text-[15px] text-ink">
          <span className="text-muted">{chapter.number}.</span> {chapter.title || "Untitled"}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-muted">
          {busy ? (
            <Badge tone="ai" dot>{status === "running" ? "Rendering" : "Queued"}</Badge>
          ) : t ? (
            <Badge tone="pass" dot>Rendered</Badge>
          ) : (
            <Badge>Not rendered</Badge>
          )}
          <span>
            {t ? formatDuration(t.duration_s) : `about ${formatDuration(chapter.estimated_s)}`}
            {" · "}{chapter.word_count.toLocaleString()} words
          </span>
        </div>
        {t && !busy && (
          <audio controls preload="none" src={t.url} className="mt-3 h-9 w-full max-w-md" aria-label={`Chapter ${chapter.number} audio`} />
        )}
        {busy && <div className="mt-3 h-1 w-full max-w-md overflow-hidden rounded-full bg-sheet"><div className="h-full w-1/3 animate-pulse rounded-full bg-gall" /></div>}
      </div>
      <Button
        variant={t ? "secondary" : "primary"}
        size="sm"
        disabled={!canRender || busy || chapter.word_count === 0}
        onClick={() => render.mutate(!!t)}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
          : t ? <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.75} />
            : <Volume2 className="h-3.5 w-3.5" strokeWidth={1.75} />}
        {t ? "Re-render" : "Render"}
      </Button>
    </li>
  );
}
