import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ChapterSummary } from "../api/client";
import StatusPill from "./StatusPill";

type Key = "number" | "title" | "status" | "word_count" | "pov";

const COLUMNS: { key: Key; label: string; align?: "right" }[] = [
  { key: "number", label: "#" },
  { key: "title", label: "Title" },
  { key: "status", label: "Status" },
  { key: "pov", label: "POV" },
  { key: "word_count", label: "Words", align: "right" },
];

export default function Outliner({ id, chapters }: { id: string; chapters: ChapterSummary[] }) {
  const navigate = useNavigate();
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "number", dir: 1 });

  const rows = [...chapters].sort((a, b) => {
    const av = a[sort.key], bv = b[sort.key];
    if (av < bv) return -1 * sort.dir;
    if (av > bv) return 1 * sort.dir;
    return 0;
  });

  const toggle = (key: Key) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: 1 }));

  return (
    <div className="overflow-hidden rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-paper-line">
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                onClick={() => toggle(c.key)}
                className={`cursor-pointer select-none px-4 py-3 text-[11px] font-bold uppercase tracking-[0.1em] text-ink-muted transition-colors hover:text-ink-text ${
                  c.align === "right" ? "text-right" : ""
                }`}
              >
                {c.label}
                {sort.key === c.key && <span className="ml-1 text-amber-deep">{sort.dir === 1 ? "↑" : "↓"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr
              key={c.number}
              onClick={() => navigate(`/projects/${id}/chapters/${c.number}`)}
              className="cursor-pointer border-b border-paper-line/60 transition-colors last:border-0 hover:bg-ink/[0.03]"
            >
              <td className="nums px-4 py-3 font-mono text-[12.5px] text-paper-muted">{c.number}</td>
              <td className="px-4 py-3 font-display text-[15px] text-ink-text">{c.title || "Untitled"}</td>
              <td className="px-4 py-3"><StatusPill status={c.status} /></td>
              <td className="px-4 py-3 text-[13px] text-ink-muted">{c.pov || "—"}</td>
              <td className="nums px-4 py-3 text-right text-[13px] text-ink-muted">{c.word_count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
