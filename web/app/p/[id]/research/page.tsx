"use client";

import { useQuery } from "@tanstack/react-query";
import { use, useState } from "react";
import { ResearchComposer } from "@/components/research/composer";
import { TaskDetail } from "@/components/research/task-detail";
import { TaskList } from "@/components/research/task-list";
import { EmptyState, Page, PageHeader, SectionLabel, Skeleton } from "@/components/ui/page";
import { isRunning, researchApi, researchKeys } from "@/lib/api/research";

// Owner: research agent. Live via useProjectEvents (research.updated -> ["p", id, "research"]).
export default function ResearchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [picked, setPicked] = useState<string | undefined>();
  const { data, isLoading, error } = useQuery({ queryKey: researchKeys.list(id), queryFn: () => researchApi.list(id) });
  const tasks = data?.tasks ?? [];
  const selected = picked && tasks.some((t) => t.id === picked) ? picked : tasks[0]?.id;
  const live = tasks.filter((t) => isRunning(t.status)).length;

  return (
    <Page wide>
      <PageHeader
        eyebrow="Research"
        title="Research swarm"
        description="Browser agents that cite every source."
        actions={data && (
          <p className="text-[13px] text-body">
            {live > 0 && <span className="text-gall">{live} running · </span>}
            {data.browsers} browsers · {data.sources} sources
          </p>
        )}
      />
      <div className="mt-10 grid gap-12 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <aside>
          <ResearchComposer projectId={id} onStarted={(t) => setPicked(t.id)} />
          <SectionLabel>Questions</SectionLabel>
          {isLoading && <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
          {error && <p className="text-[14px] text-fail">Couldn&apos;t load research. Is the server running?</p>}
          {data && tasks.length === 0 && <p className="text-[14px] text-muted">No questions yet. Ask one above.</p>}
          {tasks.length > 0 && <TaskList tasks={tasks} selected={selected} onSelect={setPicked} />}
          {data && (
            <p className="mt-4 text-[12px] text-muted">
              Reading with {data.backend === "playwright" ? "headless Chromium" : "a lightweight fetcher"} · search by {data.search_provider}
            </p>
          )}
        </aside>
        <section className="min-w-0">
          {selected ? (
            <TaskDetail key={selected} projectId={id} taskId={selected} onDeleted={() => setPicked(undefined)} />
          ) : (
            !isLoading && (
              <EmptyState
                title="Ask about anything your book needs to get right"
                body="Period details, places, professions. The swarm splits your question, reads the web in parallel and quotes every source."
              />
            )
          )}
        </section>
      </div>
    </Page>
  );
}
