"use client";

import { useQuery } from "@tanstack/react-query";
import { use } from "react";
import { FindingRow, SEVERITY_LABEL } from "@/components/manuscript/findings";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { bk, bookApi, type Severity } from "@/lib/api/book";

export default function ContinuityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const q = useQuery({ queryKey: bk.continuity(id), queryFn: () => bookApi.continuity(id), staleTime: 0 });
  const findings = q.data?.findings ?? [];
  const groups = (["critical", "warning", "info"] as Severity[]).filter((s) => findings.some((f) => f.severity === s));

  return (
    <Page>
      <PageHeader eyebrow="Guardian" title="Continuity"
        description="Deterministic checks of the manuscript against the Codex and plot threads. Mark a finding intentional and every agent learns the ruling." />

      {q.data && (
        <div className="mt-8 flex gap-10 border-y border-rule py-5">
          {(["critical", "warning", "info"] as Severity[]).map((s) => (
            <div key={s}>
              <p className="font-display text-[28px] font-bold tracking-[-0.02em]">{q.data.counts[s]}</p>
              <p className="text-[13px] text-body">{SEVERITY_LABEL[s].toLowerCase()}</p>
            </div>
          ))}
        </div>
      )}
      {q.isLoading && <Skeleton className="mt-8 h-40" />}
      {q.error && <p className="mt-8 text-[14px] text-fail">{String(q.error)}</p>}
      {q.data && findings.length === 0 && (
        <div className="mt-10"><EmptyState title="All clear" body="Nothing in the manuscript contradicts the Codex right now." /></div>
      )}

      {groups.map((s) => (
        <section key={s} className="mt-10">
          <h2 className="label mb-1">{SEVERITY_LABEL[s]}</h2>
          <ul>{findings.filter((f) => f.severity === s).map((f) => <FindingRow key={f.key} projectId={id} finding={f} />)}</ul>
        </section>
      ))}
    </Page>
  );
}
