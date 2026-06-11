import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ProjectDetail, type ChapterSummary } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
  }, [id]);

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load: {error}
        </div>
      </div>
    );
  if (!project) return <div className="px-10 py-12 text-ink-muted">Loading…</div>;

  const words = chapters.reduce((s, c) => s + c.word_count, 0);
  const drafted = chapters.filter((c) => c.status !== "planned").length;

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
      >
        ← Library
      </Link>

      <header className="mb-9 border-b border-paper-line pb-8">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-amber-deep">
          {project.genre}
        </p>
        <h1 className="font-display text-[38px] font-semibold leading-tight tracking-tight text-ink-text">
          {project.title}
        </h1>
        <p className="mt-2 text-[14px] text-ink-muted">by {project.author || "Unknown"}</p>

        <div className="mt-7 flex flex-wrap gap-8">
          <Stat label="Chapters" value={String(project.chapter_count)} />
          <Stat label="Written" value={`${drafted}/${project.chapter_count || 0}`} />
          <Stat label="Words" value={words.toLocaleString()} />
        </div>
      </header>

      <h2 className="mb-5 font-display text-[22px] font-semibold tracking-tight text-ink-text">
        Chapters
      </h2>
      <ChapterBoard chapters={chapters} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="nums font-display text-[26px] font-semibold leading-none text-ink-text">
        {value}
      </div>
      <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
        {label}
      </div>
    </div>
  );
}
