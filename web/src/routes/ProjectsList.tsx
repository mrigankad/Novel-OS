import { useEffect, useState } from "react";
import { api, type ProjectSummary } from "../api/client";
import ProjectCard from "../components/ProjectCard";

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <header className="mb-10">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.2em] text-amber-deep">
          Library
        </p>
        <h1 className="font-display text-[40px] font-semibold leading-none tracking-tight text-ink-text">
          Your manuscripts
        </h1>
        <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-muted">
          Every project is a living workspace — outlines, drafts, characters and continuity,
          orchestrated by your agent pipeline.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load projects: {error}
        </div>
      )}

      {!error && !projects && <SkeletonGrid />}

      {!error && projects && projects.length === 0 && (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-14 text-center">
          <p className="font-display text-[20px] text-ink-text">No manuscripts yet</p>
          <p className="mt-2 text-[14px] text-ink-muted">
            Start one from the terminal:&nbsp;
            <code className="rounded bg-ink/5 px-1.5 py-0.5 font-mono text-[12.5px]">
              python core/orchestrator.py init …
            </code>
          </p>
        </div>
      )}

      {projects && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-44 animate-pulse rounded-xl border border-paper-line bg-paper-card/70"
        />
      ))}
    </div>
  );
}
