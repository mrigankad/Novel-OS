"use client";

import { clsx } from "clsx";
import { isRunning, type ResearchStatus, type ResearchTask } from "@/lib/api/research";

const DOT: Record<ResearchStatus, string> = {
  queued: "bg-gall",
  browsing: "bg-gall",
  synthesizing: "bg-gall",
  done: "bg-pass",
  failed: "bg-fail",
  cancelled: "bg-muted",
};

const LABEL: Record<ResearchStatus, string> = {
  queued: "Queued",
  browsing: "Browsing",
  synthesizing: "Synthesizing",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function StatusDot({ status }: { status: ResearchStatus }) {
  return <span aria-label={LABEL[status]} className={clsx("inline-block h-2 w-2 shrink-0 rounded-full", DOT[status])} />;
}

export function TaskList({ tasks, selected, onSelect }: {
  tasks: ResearchTask[]; selected?: string; onSelect: (id: string) => void;
}) {
  return (
    <ul className="divide-y divide-rule border-y border-rule">
      {tasks.map((t) => (
        <li key={t.id}>
          <button
            type="button"
            onClick={() => onSelect(t.id)}
            className={clsx(
              "flex w-full items-start gap-3 px-2 py-3 text-left transition-colors hover:bg-sheet",
              selected === t.id && "bg-sheet",
            )}
          >
            <span className="mt-[7px]"><StatusDot status={t.status} /></span>
            <span className="min-w-0 flex-1">
              <span className="line-clamp-2 text-[14px] font-medium text-ink">{t.question}</span>
              <span className={clsx("mt-0.5 block truncate text-[12px]", isRunning(t.status) ? "text-gall" : "text-muted")}>
                {isRunning(t.status) ? t.progress || LABEL[t.status] : `${LABEL[t.status]} · ${t.source_count} sources`}
                {t.chapter != null && ` · Ch. ${t.chapter}`}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
