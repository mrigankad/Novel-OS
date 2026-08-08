import {
  SUGGESTION_INSERT,
  acceptAllSuggestions,
  acceptSuggestion,
  listSuggestions,
  rejectAllSuggestions,
  rejectSuggestion,
} from "../lib/trackChanges";
import type { PMDoc } from "../lib/richText";
import Icon from "./Icon";

/**
 * Pending track changes with accept/reject (PLAN.md P5.1).
 *
 * Every resolution goes back through `onChange` as a whole new document rather
 * than mutating the editor in place, so accepting a change is an ordinary edit:
 * it is dirty, it autosaves, and Ctrl-Z undoes it.
 */
export default function SuggestionsPanel({
  doc,
  onChange,
}: {
  doc: PMDoc;
  onChange: (doc: PMDoc) => void;
}) {
  const suggestions = listSuggestions(doc);
  if (suggestions.length === 0) return null;

  return (
    <section
      aria-label="Pending changes"
      className="mt-4 rounded-2xl border border-[rgba(104,103,234,0.22)] bg-[rgba(104,103,234,0.05)] px-4 py-3"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[12px] font-semibold text-ink-text">
          <Icon name="git-branch" className="h-3.5 w-3.5 text-[var(--color-violet)]" />
          {suggestions.length} pending {suggestions.length === 1 ? "change" : "changes"}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-ghost px-2.5 py-1 text-[12px]"
            onClick={() => onChange(rejectAllSuggestions(doc))}
          >
            Reject all
          </button>
          <button
            type="button"
            className="btn-secondary px-2.5 py-1 text-[12px]"
            onClick={() => onChange(acceptAllSuggestions(doc))}
          >
            Accept all
          </button>
        </div>
      </div>

      <ul className="space-y-1.5">
        {suggestions.map((s) => {
          const isInsert = s.kind === SUGGESTION_INSERT;
          return (
            <li
              key={s.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-[rgba(74,91,133,0.12)] bg-white/70 px-3 py-2"
            >
              <span
                className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                  isInsert
                    ? "bg-[rgba(52,168,120,0.14)] text-[#1f7a55]"
                    : "bg-[rgba(200,80,100,0.14)] text-[#a8324a]"
                }`}
              >
                {isInsert ? "Insert" : "Delete"}
              </span>
              <span
                className={`min-w-0 flex-1 truncate text-[13px] text-ink-text ${
                  isInsert ? "" : "line-through decoration-[#a8324a]/60"
                }`}
                title={s.text}
              >
                {s.text}
              </span>
              {s.author && (
                <span className="shrink-0 text-[11.5px] text-ink-muted">{s.author}</span>
              )}
              <span className="flex shrink-0 gap-1">
                <button
                  type="button"
                  aria-label={`Reject ${isInsert ? "insertion" : "deletion"}`}
                  className="btn-ghost px-2 py-0.5 text-[12px]"
                  onClick={() => onChange(rejectSuggestion(doc, s.id))}
                >
                  Reject
                </button>
                <button
                  type="button"
                  aria-label={`Accept ${isInsert ? "insertion" : "deletion"}`}
                  className="btn-secondary px-2 py-0.5 text-[12px]"
                  onClick={() => onChange(acceptSuggestion(doc, s.id))}
                >
                  Accept
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
