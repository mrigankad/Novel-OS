import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ChapterSummary } from "../api/client";
import ChapterPipelineStatus from "./ChapterPipelineStatus";
import DeleteButton from "./DeleteButton";
import { pipelineStepFromSummary } from "../lib/chapterPipeline";

type Key = "number" | "title" | "pipeline_step" | "word_count" | "pov";

const COLUMNS: { key: Key | "actions"; label: string; align?: "right"; sortable?: boolean }[] = [
  { key: "number", label: "#", sortable: true },
  { key: "title", label: "Title", sortable: true },
  { key: "pipeline_step", label: "Status", sortable: true },
  { key: "pov", label: "POV", sortable: true },
  { key: "word_count", label: "Words", align: "right", sortable: true },
  { key: "actions", label: "", sortable: false },
];

export default function Outliner({
  id,
  chapters,
  onDelete,
  onRenumber,
}: {
  id: string;
  chapters: ChapterSummary[];
  onDelete?: (c: ChapterSummary) => void;
  onRenumber?: (c: ChapterSummary) => void;
}) {
  const navigate = useNavigate();
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "number", dir: 1 });

  const rows = [...chapters].sort((a, b) => {
    let av: string | number;
    let bv: string | number;
    if (sort.key === "pipeline_step") {
      av = pipelineStepFromSummary(a);
      bv = pipelineStepFromSummary(b);
    } else {
      av = a[sort.key];
      bv = b[sort.key];
    }
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
                onClick={() => c.sortable && c.key !== "actions" && toggle(c.key as Key)}
                className={`select-none px-4 py-3 text-[11px] font-bold uppercase tracking-[0.1em] text-ink-muted ${
                  c.sortable ? "cursor-pointer transition-colors hover:text-ink-text" : ""
                } ${c.align === "right" ? "text-right" : ""}`}
              >
                {c.label}
                {c.sortable && sort.key === c.key && (
                  <span className="ml-1 text-amber-deep">{sort.dir === 1 ? "↑" : "↓"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr
              key={c.number}
              onClick={() => navigate(`/projects/${id}/chapters/${c.number}`)}
              className="group cursor-pointer border-b border-paper-line/60 transition-colors last:border-0 hover:bg-ink/[0.03]"
            >
              <td className="nums px-4 py-3 font-mono text-[12.5px] text-paper-muted">{c.number}</td>
              <td className="px-4 py-3 font-display text-[15px] text-ink-text">{c.title || "Untitled"}</td>
              <td className="px-4 py-3"><ChapterPipelineStatus chapter={c} /></td>
              <td className="px-4 py-3 text-[13px] text-ink-muted">{c.pov || "—"}</td>
              <td className="nums px-4 py-3 text-right text-[13px] text-ink-muted">{c.word_count.toLocaleString()}</td>
              <td className="px-2 py-2 text-right">
                <div className="flex justify-end gap-0.5">
                  {onRenumber && (
                    <button type="button" title="Renumber"
                            onClick={(e) => { e.stopPropagation(); onRenumber(c); }}
                            className="rounded-md px-2 py-1 text-[11px] font-bold text-ink-muted opacity-0 group-hover:opacity-100 hover:text-ink-text">
                      #
                    </button>
                  )}
                  {onDelete && (
                    <DeleteButton
                      label={`Delete chapter ${c.number}`}
                      title="Delete chapter"
                      message={`Delete chapter ${c.number}${c.title ? `: "${c.title}"` : ""}? All outline, draft, and manuscript files for this chapter will be removed.`}
                      confirmLabel="Delete chapter"
                      onConfirm={() => onDelete(c)}
                      className="opacity-0 group-hover:opacity-100"
                    />
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
