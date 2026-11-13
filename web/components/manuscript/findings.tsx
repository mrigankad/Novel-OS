"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ArrowUpRight, Check } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { bookApi, type Finding, type Severity } from "@/lib/api/book";

export const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", warning: "Warnings", info: "Notes" };
const SEVERITY_TONE: Record<Severity, string> = { critical: "bg-fail", warning: "bg-warn", info: "bg-muted" };

export function fixHref(projectId: string, f: Finding): string | null {
  if (!f.fix) return null;
  if (f.fix.type === "chapter") return `/p/${projectId}/write/${f.fix.chapter}?mode=revise`;
  return `/p/${projectId}/codex?entry=${f.fix.id}`;
}

export function FindingRow({ projectId, finding, compact }: { projectId: string; finding: Finding; compact?: boolean }) {
  const qc = useQueryClient();
  const toast = useToast();
  const exempt = useMutation({
    mutationFn: () => bookApi.exempt(projectId, finding),
    onSuccess: () => {
      toast("Marked intentional. Agents will remember the ruling.", "success");
      void qc.invalidateQueries({ queryKey: ["p", projectId, "codex", "continuity"] });
      void qc.invalidateQueries({ queryKey: ["p", projectId, "memory"] });
    },
    onError: (e) => toast(String(e), "error"),
  });
  const href = fixHref(projectId, finding);
  return (
    <li className={clsx("flex gap-3 border-b border-rule last:border-b-0", compact ? "py-3" : "py-4")}>
      <span className={clsx("mt-[7px] h-2 w-2 shrink-0 rounded-full", SEVERITY_TONE[finding.severity])} />
      <div className="min-w-0 flex-1">
        <p className={clsx("text-ink", compact ? "text-[13px]" : "text-[15px]")}>{finding.message}</p>
        {finding.suggestion && <p className="mt-1 text-[13px] text-body">{finding.suggestion}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {href && !compact && (
            <Link href={href} className="inline-flex h-8 items-center gap-1 rounded-[10px] px-3 text-[13px] font-semibold text-ink hover:bg-sheet">
              {finding.fix?.type === "chapter" ? `Open chapter ${finding.fix.chapter}` : "Open in Codex"}
              <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.75} />
            </Link>
          )}
          <Button variant="ghost" size="sm" onClick={() => exempt.mutate()} disabled={exempt.isPending}>
            <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> This is intentional
          </Button>
        </div>
      </div>
    </li>
  );
}
