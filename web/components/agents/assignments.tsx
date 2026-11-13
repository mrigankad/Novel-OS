"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Check } from "lucide-react";
import { EmptyState } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { agentsApi, type Agent, type RoomChapter } from "@/lib/api/agents";
import { AgentGlyph } from "./agent-icon";

/** Chapters (rows) by writers (columns): click a cell to choose who drafts that chapter. */
export function Assignments({ projectId, cast, chapters, onOpenAgent }: {
  projectId: string; cast: Agent[]; chapters: RoomChapter[]; onOpenAgent: (a: Agent) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const writers = cast.filter((a) => a.role === "scribe" || a.role === "custom");
  const fallback = writers.find((a) => a.role === "scribe" && a.enabled);
  const assign = useMutation({
    mutationFn: ({ n, aid }: { n: number; aid: string | null }) => agentsApi.assign(projectId, n, aid),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["p", projectId, "agent"] });
      void qc.invalidateQueries({ queryKey: ["p", projectId, "chapter"] });
      void qc.invalidateQueries({ queryKey: ["p", projectId, "run"] });
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  if (chapters.length === 0) return <EmptyState title="No chapters yet" body="Add chapters in the manuscript, then assign who writes each one." />;
  return (
    <div className="mx-auto max-w-4xl">
      <p className="mb-4 text-[14px] leading-relaxed text-body">
        Choose who drafts each chapter. Unassigned chapters go to {fallback ? <span className="font-semibold text-ink">{fallback.name}</span> : "the first Scribe"}.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-rule">
              <th className="py-2 pr-4 text-left font-semibold text-muted">Chapter</th>
              {writers.map((a) => (
                <th key={a.id} className="px-2 py-2 font-semibold text-ink">
                  <button type="button" onClick={() => onOpenAgent(a)} className="mx-auto flex flex-col items-center gap-1 hover:text-gall">
                    <AgentGlyph role={a.role} size="sm" />
                    <span className={clsx("max-w-[120px] truncate", !a.enabled && "text-muted line-through")}>{a.name}</span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {chapters.map((c) => (
              <tr key={c.number} className="border-b border-rule last:border-0">
                <td className="max-w-[260px] truncate py-2 pr-4 text-ink">
                  <span className="font-semibold">{c.number}.</span> <span className="text-body">{c.title || "Untitled"}</span>
                </td>
                {writers.map((a) => {
                  const on = c.assigned_agent_id === a.id;
                  const implicit = !c.assigned_agent_id && a.id === fallback?.id;
                  return (
                    <td key={a.id} className="px-2 py-1.5 text-center">
                      <button type="button" disabled={assign.isPending}
                        aria-label={`${on ? "Unassign" : "Assign"} ${a.name} ${on ? "from" : "to"} chapter ${c.number}`}
                        aria-pressed={on}
                        title={implicit ? "Default writer" : undefined}
                        onClick={() => assign.mutate({ n: c.number, aid: on ? null : a.id })}
                        className={clsx("inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors",
                          on ? "border-ink bg-ink text-white"
                            : implicit ? "border-dashed border-body text-body hover:border-ink"
                              : "border-rule-strong text-transparent hover:border-body hover:text-muted")}>
                        <Check className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
