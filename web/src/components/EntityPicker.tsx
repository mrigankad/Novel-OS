import { useId, useMemo, useState } from "react";

export type EntityOption = {
  id: string;
  name: string;
  meta?: string;
};

/**
 * Searchable single-pick list for people/places — not a buried dropdown.
 * Best when the set grows beyond a glanceable chip row.
 */
export default function EntityPicker({
  label,
  value,
  onChange,
  options,
  placeholder = "Search…",
  excludeId,
}: {
  label: string;
  value: string;
  onChange: (id: string) => void;
  options: EntityOption[];
  placeholder?: string;
  excludeId?: string;
}) {
  const listId = useId();
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const pool = excludeId ? options.filter((o) => o.id !== excludeId) : options;
    if (!needle) return pool;
    return pool.filter(
      (o) =>
        o.name.toLowerCase().includes(needle) ||
        (o.meta ?? "").toLowerCase().includes(needle),
    );
  }, [options, q, excludeId]);

  const selected = options.find((o) => o.id === value);

  return (
    <div>
      {selected && (
        <div className="mb-2 flex items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-full bg-[rgba(104,103,234,0.12)] px-3 py-1 text-[13px] font-medium text-[var(--color-violet)]">
            {selected.name}
          </span>
          <button
            type="button"
            onClick={() => onChange("")}
            className="text-[12px] text-ink-muted hover:text-ink"
          >
            Clear
          </button>
        </div>
      )}
      <input
        className="w-full rounded-full border border-[rgba(96,112,153,0.17)] bg-white/60 px-4 py-2.5 text-[14px] font-medium text-ink-text shadow-[inset_0_1px_3px_rgba(48,62,98,0.06)] placeholder:text-paper-muted focus:border-[rgba(104,103,234,0.38)] focus:bg-white focus:outline-none focus:shadow-[0_0_0_5px_rgba(104,103,234,0.09)]"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        aria-label={label}
        aria-controls={listId}
        autoComplete="off"
      />
      <ul
        id={listId}
        role="listbox"
        aria-label={label}
        className="mt-2 max-h-36 space-y-0.5 overflow-y-auto rounded-2xl border border-[rgba(74,91,133,0.1)] bg-white/70 p-1"
      >
        {filtered.length === 0 && (
          <li className="px-3 py-4 text-center text-[12.5px] text-ink-muted">No matches</li>
        )}
        {filtered.map((o) => {
          const on = o.id === value;
          return (
            <li key={o.id}>
              <button
                type="button"
                role="option"
                aria-selected={on}
                onClick={() => {
                  onChange(o.id);
                  setQ("");
                }}
                className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-[13.5px] transition-colors ${
                  on
                    ? "bg-[rgba(104,103,234,0.12)] font-medium text-[var(--color-violet)]"
                    : "text-ink-text hover:bg-[rgba(74,91,133,0.06)]"
                }`}
              >
                <span>{o.name}</span>
                {o.meta && <span className="text-[11px] text-ink-muted">{o.meta}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
