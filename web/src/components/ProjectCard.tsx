import { Link } from "react-router-dom";
import type { ProjectSummary } from "../api/client";
import StatusPill from "./StatusPill";
import Icon from "./Icon";

const TILES = ["violet", "blue", "cyan", "amber", "rose", "indigo"] as const;
const TILE_CLASS: Record<(typeof TILES)[number], string> = {
  violet: "text-[#625edb] bg-[#eeedff]",
  blue: "text-[#3974db] bg-[#e8f1ff]",
  cyan: "text-[#1591ab] bg-[#e3f8fa]",
  amber: "text-[#c47a1b] bg-[#fff2dc]",
  rose: "text-[#c85177] bg-[#ffeaf1]",
  indigo: "text-[#4f69cf] bg-[#e9edff]",
};

function tileFor(id: string) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h + id.charCodeAt(i) * (i + 1)) % TILES.length;
  return TILES[h];
}

function when(iso: string | null | undefined) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return null;
  }
}

export default function ProjectCard({ p }: { p: ProjectSummary }) {
  const tile = tileFor(p.id);
  const progress = (p.target_word_count && p.target_word_count > 0)
    ? Math.round(((p.word_count ?? 0) / p.target_word_count) * 100)
    : p.chapter_count
      ? Math.round(((p.drafted_count ?? 0) / p.chapter_count) * 100)
      : 0;
  const touched = when(p.updated_at);

  return (
    <Link
      to={`/projects/${p.id}`}
      className="glass-card group flex min-h-[168px] flex-col p-5 text-left"
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-[18px] text-[22px] font-bold ${TILE_CLASS[tile]}`}
        >
          {p.title.charAt(0).toUpperCase()}
        </span>
        <div className="flex flex-col items-end gap-1.5">
          <StatusPill status={p.status} />
          {p.content_rating === "mature" && (
            <span className="rounded-full border border-[rgba(200,81,119,0.25)] bg-[#ffeaf1] px-2 py-0.5 text-[10px] font-medium text-[#c85177]">
              Mature
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 min-w-0 flex-1">
        <span className="mb-1.5 block line-clamp-2 text-[17px] font-semibold leading-snug tracking-[-0.02em] text-ink-text">
          {p.title}
        </span>
        <span className="block truncate text-[13px] text-ink-muted">
          {p.genre || "Untitled genre"}
          {p.author ? ` · ${p.author}` : ""}
        </span>
      </div>

      <div className="mt-4">
        <div className="mb-2 h-1 overflow-hidden rounded-full bg-[rgba(74,91,133,0.1)]">
          <div
            className="h-full rounded-full bg-[var(--color-violet)] transition-all"
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-[12px] text-ink-muted">
          <span className="nums">
            {(p.word_count ?? 0).toLocaleString()} words · {p.drafted_count ?? 0}/{p.chapter_count} chapters
          </span>
          <span className="flex items-center gap-1.5">
            {touched && <span>{touched}</span>}
            <Icon
              name="chevron-right"
              className="h-3.5 w-3.5 text-paper-muted transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-[var(--color-violet)]"
            />
          </span>
        </div>
      </div>
    </Link>
  );
}
