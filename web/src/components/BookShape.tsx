import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type BookShapeReport } from "../api/client";
import Icon from "./Icon";

/**
 * The shape of the book (design spec §4.3).
 *
 * One bar per chapter, height by how much measurably changed in it, flat
 * chapters greyed, and any sagging run marked underneath. Middles are where
 * books die, and a writer cannot see the sag from inside chapter 34 - but they
 * can see it in fifteen bars.
 *
 * Everything shown here is deterministic: the engine counts plot advances,
 * character development, emotional beats, new information, and threads touched.
 * No model is asked whether the book drags. In-house SVG, per the standing
 * rule that analytics visuals do not justify a chart library.
 */
export default function BookShape({ projectId }: { projectId: string }) {
  const [report, setReport] = useState<BookShapeReport | null>(null);

  const load = useCallback(() => {
    api.bookShape(projectId).then(setReport).catch(() => setReport(null));
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const chapters = report?.chapters ?? [];
  if (chapters.length === 0) return null;

  const peak = Math.max(1, ...chapters.map((c) => c.movement));
  const stalled = new Set(report?.stalls.flatMap((s) => s.chapters) ?? []);

  return (
    <section
      aria-label="Shape of the book"
      className="mb-6 rounded-[24px] border border-[rgba(74,91,133,0.12)] bg-white/55 px-5 py-5 backdrop-blur-md"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold tracking-tight text-ink-text">
            Shape of the book
          </h2>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">
            How much changes in each chapter · plot, character, information, threads
          </p>
        </div>
        <button type="button" onClick={load} className="btn-ghost text-[12px]">
          Refresh
        </button>
      </div>

      <div
        role="list"
        aria-label="Chapters"
        className="flex items-end gap-[3px] overflow-x-auto pb-1"
      >
        {chapters.map((c) => {
          const height = c.written
            ? Math.max(6, Math.round((c.movement / peak) * 64))
            : 4;
          const sagging = stalled.has(c.number);
          return (
            <Link
              key={c.number}
              to={`/projects/${projectId}/chapters/${c.number}`}
              role="listitem"
              aria-label={
                `Chapter ${c.number}${c.title ? `: ${c.title}` : ""} — ` +
                (c.written
                  ? `${c.movement} changes${sagging ? ", part of a stalled run" : ""}`
                  : "not written yet")
              }
              title={
                `Ch ${c.number}${c.title ? ` · ${c.title}` : ""}\n` +
                (c.written ? `${c.movement} changes` : "Not written yet")
              }
              className="group flex w-[14px] shrink-0 flex-col items-center gap-1"
            >
              <span
                style={{ height }}
                className={`w-full rounded-sm transition-colors ${
                  !c.written
                    ? "bg-paper-line"
                    : sagging
                      ? "bg-[#e2a0b2] group-hover:bg-[#c85177]"
                      : "bg-[var(--color-violet)]/60 group-hover:bg-[var(--color-violet)]"
                }`}
              />
              <span className="nums text-[9px] text-paper-muted">{c.number}</span>
            </Link>
          );
        })}
      </div>

      {(report?.stalls.length ?? 0) > 0 && (
        <ul
          aria-label="Stalled stretches"
          className="mt-4 space-y-1.5 border-t border-[rgba(74,91,133,0.1)] pt-3"
        >
          {report?.stalls.map((s) => (
            <li
              key={`${s.start}-${s.end}`}
              className="flex flex-wrap items-center gap-2 text-[12.5px]"
            >
              <Icon name="triangle-alert" className="h-3.5 w-3.5 shrink-0 text-[#c85177]" />
              <Link
                to={`/projects/${projectId}/chapters/${s.start}`}
                className="font-medium text-ink-text underline-offset-2 hover:underline"
              >
                Ch {s.start}–{s.end}
              </Link>
              <span className="text-ink-muted">{s.reason}.</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
