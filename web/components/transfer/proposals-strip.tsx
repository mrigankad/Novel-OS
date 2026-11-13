"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { bk } from "@/lib/api/book";
import { tk, transferApi } from "@/lib/api/transfer";

const FINISHED = ["done", "failed", "cancelled"];
const KIND: Record<string, string> = {
  character: "Character", location: "Place", item: "Item", lore: "Lore", faction: "Faction", event: "Event",
};

/** "Suggested from your chapters": Codex entries the Architect found in the prose. */
export function ProposalsStrip({ id }: { id: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [runId, setRunId] = useState<string | null>(null);
  const list = useQuery({ queryKey: tk.proposals(id), queryFn: () => transferApi.proposals(id) });
  const run = useQuery({
    queryKey: tk.run(id, runId ?? "none"),
    queryFn: async () => {
      const r = await transferApi.run(id, runId!);
      if (FINISHED.includes(r.status)) {
        void qc.invalidateQueries({ queryKey: tk.proposals(id) });
        if (r.status === "failed") toast(`Couldn't read the chapters: ${r.error ?? "unknown error"}`, "error");
        else if (!r.output?.proposals) toast("Nothing new to add. The Codex is up to date.", "info");
        setRunId(null);
      }
      return r;
    },
    enabled: !!runId,
    refetchInterval: 1500,
  });
  const running = !!runId && !FINISHED.includes(run.data?.status ?? "");

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: tk.proposals(id) });
    void qc.invalidateQueries({ queryKey: bk.codexAll(id) });
  };
  const find = useMutation({
    mutationFn: () => transferApi.findProposals(id),
    onSuccess: (r) => setRunId(r.run_id),
    onError: (e) => toast(String(e), "error"),
  });
  const accept = useMutation({
    mutationFn: (pid: string) => transferApi.accept(id, pid),
    onSuccess: refresh,
    onError: (e) => { toast(String(e), "error"); refresh(); },
  });
  const dismiss = useMutation({
    mutationFn: (pid: string) => transferApi.dismiss(id, pid),
    onSuccess: refresh,
    onError: (e) => { toast(String(e), "error"); refresh(); },
  });

  const items = list.data ?? [];
  return (
    <section className="mt-8 border-b border-rule pb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[15px] font-semibold text-ink">Suggested from your chapters</p>
          <p className="text-[13px] text-body">
            {running ? "The Architect is reading the chapters for names the Codex doesn't have yet…"
              : items.length ? `${items.length} name${items.length === 1 ? "" : "s"} the Codex doesn't have yet.`
              : "Names that recur in the prose but aren't in the Codex show up here."}
          </p>
        </div>
        <Button variant="ai" size="sm" onClick={() => find.mutate()} disabled={running || find.isPending}>
          <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} />
          {running ? "Reading…" : "Find new entries"}
        </Button>
      </div>

      {items.length > 0 && (
        <ul className="mt-4 flex gap-4 overflow-x-auto pb-1">
          {items.map((p) => (
            <li key={p.id} className="flex w-[280px] shrink-0 flex-col rounded-[12px] bg-sheet p-4">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-[15px] font-semibold text-ink">{p.name}</p>
                <span className="shrink-0 text-[12px] text-body">
                  {KIND[p.kind] ?? p.kind}{p.first_chapter ? ` · ch ${p.first_chapter}` : ""}
                </span>
              </div>
              {p.summary && <p className="mt-1.5 line-clamp-2 text-[13px] text-body">{p.summary}</p>}
              {p.evidence && (
                <p className="mt-2 line-clamp-3 font-prose text-[14px] italic leading-snug text-ink/80">&ldquo;{p.evidence}&rdquo;</p>
              )}
              <div className="mt-auto flex gap-2 pt-3">
                <Button size="sm" onClick={() => accept.mutate(p.id)} disabled={accept.isPending || dismiss.isPending}>
                  <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Accept
                </Button>
                <Button size="sm" variant="ghost" onClick={() => dismiss.mutate(p.id)} disabled={accept.isPending || dismiss.isPending}>
                  <X className="h-3.5 w-3.5" strokeWidth={1.75} /> Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
