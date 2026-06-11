import { Link, useParams } from "react-router-dom";
import type { ChapterSummary } from "../api/client";
import StatusPill from "./StatusPill";

export default function ChapterBoard({ chapters }: { chapters: ChapterSummary[] }) {
  const { id } = useParams();

  if (chapters.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-12 text-center">
        <p className="font-display text-[18px] text-ink-text">No chapters planned yet</p>
        <p className="mt-2 text-[13.5px] text-ink-muted">
          Plan one with <code className="font-mono text-[12px]">plan chapter --number 1</code>
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {chapters.map((c) => (
        <Link
          key={c.number}
          to={`/projects/${id}/chapters/${c.number}`}
          className="group relative flex flex-col rounded-xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)]"
        >
          <div className="flex items-start justify-between">
            <span className="font-display text-[13px] font-semibold uppercase tracking-[0.12em] text-amber-deep">
              Ch {c.number}
            </span>
            <StatusPill status={c.status} />
          </div>
          <span className="mt-3 font-display text-[19px] font-medium leading-snug text-ink-text transition-colors group-hover:text-amber-deep">
            {c.title || "Untitled"}
          </span>
          <div className="mt-5 flex items-center gap-3 text-[12.5px] text-ink-muted">
            <span className="nums">{c.word_count.toLocaleString()} words</span>
            {c.pov && (
              <>
                <span className="text-paper-muted">·</span>
                <span className="truncate">POV {c.pov}</span>
              </>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
