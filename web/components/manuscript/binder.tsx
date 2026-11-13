"use client";

import { clsx } from "clsx";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { StatusDot } from "@/components/manuscript/bits";
import { actLabel, type ChapterRow } from "@/lib/api/book";

export function Binder({
  projectId, chapters, current, open, onToggle,
}: { projectId: string; chapters: ChapterRow[]; current: number; open: boolean; onToggle: () => void }) {
  const acts = [...new Set(chapters.map((c) => c.act))].sort((a, b) => a - b);
  if (!open) {
    return (
      <div className="shrink-0 border-r border-rule p-2">
        <button type="button" onClick={onToggle} aria-label="Show chapters" className="rounded-[8px] p-2 text-muted hover:bg-sheet hover:text-ink">
          <PanelLeftOpen className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>
    );
  }
  return (
    <nav aria-label="Chapters" className="w-[232px] shrink-0 overflow-y-auto border-r border-rule px-3 py-4">
      <div className="mb-3 flex items-center justify-between px-2">
        <span className="label">Binder</span>
        <button type="button" onClick={onToggle} aria-label="Hide chapters" className="rounded-[8px] p-1.5 text-muted hover:bg-sheet hover:text-ink">
          <PanelLeftClose className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>
      {acts.map((act) => (
        <div key={act} className="mb-4">
          <p className="px-2 pb-1 text-[12px] font-semibold text-body">{actLabel(act)}</p>
          {chapters.filter((c) => c.act === act).map((c) => (
            <Link key={c.id} href={`/p/${projectId}/write/${c.number}`}
              className={clsx("flex items-center gap-2.5 rounded-[8px] px-2 py-1.5 text-[13px]",
                c.number === current ? "bg-sheet font-semibold text-ink" : "text-body hover:bg-sheet hover:text-ink")}>
              <StatusDot status={c.status} />
              <span className="w-4 shrink-0 text-muted">{c.number}</span>
              <span className="truncate">{c.title || "Untitled"}</span>
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}
