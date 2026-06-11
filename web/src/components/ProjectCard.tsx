import { Link } from "react-router-dom";
import type { ProjectSummary } from "../api/client";
import StatusPill from "./StatusPill";

export default function ProjectCard({ p }: { p: ProjectSummary }) {
  return (
    <Link
      to={`/projects/${p.id}`}
      className="group relative flex flex-col overflow-hidden rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]"
    >
      {/* book spine */}
      <span className="absolute inset-y-0 left-0 w-1.5 bg-gradient-to-b from-amber to-amber-deep" />
      <div className="flex flex-1 flex-col p-6 pl-7">
        <span className="mb-3 inline-flex w-fit items-center rounded-md bg-ink/5 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
          {p.genre || "Untitled genre"}
        </span>
        <h3 className="font-display text-[22px] font-semibold leading-snug tracking-tight text-ink-text transition-colors group-hover:text-amber-deep">
          {p.title}
        </h3>
        <div className="mt-auto flex items-center justify-between pt-6">
          <span className="nums text-[13px] font-medium text-ink-muted">{p.chapter_count} chapters</span>
          <StatusPill status={p.status} />
        </div>
      </div>
    </Link>
  );
}
