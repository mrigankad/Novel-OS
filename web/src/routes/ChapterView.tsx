import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, type ChapterDetail, type ChapterSummary } from "../api/client";
import StatusPill from "../components/StatusPill";

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const num = Number(n);
  const [chapter, setChapter] = useState<ChapterDetail | null>(null);
  const [siblings, setSiblings] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.chapter(id, num).then(setChapter).catch((e) => setError(String(e)));
    // binder is supplementary — never let its failure blank the page
    api.chapters(id).then(setSiblings).catch(() => setSiblings([]));
  }, [id, num]);

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load: {error}
        </div>
      </div>
    );
  if (!chapter) return <div className="px-10 py-12 text-ink-muted">Loading…</div>;

  return (
    <div className="flex h-full">
      {/* Binder rail */}
      <nav className="hidden w-[210px] shrink-0 flex-col border-r border-paper-line bg-paper-card/40 lg:flex">
        <div className="px-5 pb-3 pt-6">
          <Link
            to={`/projects/${id}`}
            className="text-[12.5px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
          >
            ← {id.replace(/-/g, " ")}
          </Link>
        </div>
        <p className="px-5 pb-2 text-[10.5px] font-bold uppercase tracking-[0.16em] text-paper-muted">
          Binder
        </p>
        <div className="flex flex-col gap-0.5 px-2.5">
          {siblings.map((c) => (
            <Link
              key={c.number}
              to={`/projects/${id}/chapters/${c.number}`}
              className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                c.number === num
                  ? "bg-amber/15 font-medium text-ink-text"
                  : "text-ink-muted hover:bg-ink/5"
              }`}
            >
              <span className="font-mono text-[11px] text-paper-muted">{c.number}</span>
              <span className="truncate">{c.title || "Untitled"}</span>
            </Link>
          ))}
        </div>
      </nav>

      {/* Editor — the manuscript page */}
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-paper-line bg-paper-card/30 px-10 py-6 backdrop-blur">
          <div className="mx-auto flex max-w-[680px] flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11.5px] font-semibold uppercase tracking-[0.16em] text-amber-deep">
                Chapter {chapter.number}
              </p>
              <h1 className="font-display text-[26px] font-semibold tracking-tight text-ink-text">
                {chapter.title || "Untitled"}
              </h1>
            </div>
            <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
              <StatusPill status={chapter.status} />
              <span>{chapter.word_count.toLocaleString()} words</span>
              {chapter.pov && <span>· POV {chapter.pov}</span>}
            </div>
          </div>
        </div>

        <div className="px-10 py-10">
          <article className="mx-auto max-w-[680px] rounded-md bg-paper-card px-12 py-14 shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
            {chapter.draft ? (
              <div className="prose-manuscript">
                <ReactMarkdown>{chapter.draft}</ReactMarkdown>
              </div>
            ) : (
              <EmptyState
                title="Draft not generated yet"
                hint="Run the Scribe to draft this chapter from its outline."
              />
            )}
          </article>
        </div>
      </div>

      {/* Inspector — the beat-sheet */}
      <aside className="hidden w-[320px] shrink-0 flex-col overflow-y-auto border-l border-paper-line bg-paper-card/40 xl:flex">
        <p className="px-6 pb-3 pt-6 text-[10.5px] font-bold uppercase tracking-[0.16em] text-paper-muted">
          Outline · Beat sheet
        </p>
        <div className="px-6 pb-10">
          <div className="rounded-lg border border-paper-line bg-[#fffef9] p-5 shadow-[var(--shadow-paper)]">
            {chapter.outline ? (
              <div className="prose-outline">
                <ReactMarkdown>{chapter.outline}</ReactMarkdown>
              </div>
            ) : (
              <EmptyState
                title="Outline not generated yet"
                hint="The Architect plans the beats before the Scribe writes."
                compact
              />
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function EmptyState({ title, hint, compact }: { title: string; hint: string; compact?: boolean }) {
  return (
    <div className={compact ? "py-4 text-center" : "py-10 text-center"}>
      <p className="font-display text-[17px] text-ink-text">{title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{hint}</p>
    </div>
  );
}
