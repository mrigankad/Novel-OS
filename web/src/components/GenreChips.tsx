import { useId, useState } from "react";
import { GENRE_OPTIONS } from "../lib/genres";

export default function GenreChips({
  selected,
  onChange,
  other,
  onOtherChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
  other: string;
  onOtherChange: (value: string) => void;
}) {
  const otherId = useId();
  const [showOther, setShowOther] = useState(Boolean(other.trim()));

  function toggle(label: string) {
    if (selected.some((s) => s.toLowerCase() === label.toLowerCase())) {
      onChange(selected.filter((s) => s.toLowerCase() !== label.toLowerCase()));
    } else {
      onChange([...selected, label]);
    }
  }

  function toggleOther() {
    if (showOther) {
      setShowOther(false);
      onOtherChange("");
    } else {
      setShowOther(true);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {GENRE_OPTIONS.map((g) => {
          const on = selected.some((s) => s.toLowerCase() === g.toLowerCase());
          return (
            <button
              key={g}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(g)}
              className={`rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors sm:px-3 sm:py-1.5 sm:text-[12.5px] ${
                on
                  ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                  : "border border-[rgba(96,112,153,0.16)] bg-white/55 text-ink-muted hover:text-ink"
              }`}
            >
              {g}
            </button>
          );
        })}
        <button
          type="button"
          aria-pressed={showOther}
          onClick={toggleOther}
          className={`rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors sm:px-3 sm:py-1.5 sm:text-[12.5px] ${
            showOther
              ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
              : "border border-[rgba(96,112,153,0.16)] bg-white/55 text-ink-muted hover:text-ink"
          }`}
        >
          Other
        </button>
      </div>
      {showOther && (
        <input
          id={otherId}
          className="mt-2.5 w-full rounded-full border border-[rgba(96,112,153,0.17)] bg-white/60 px-4 py-2.5 text-[14px] font-medium text-ink-text shadow-[inset_0_1px_3px_rgba(48,62,98,0.06)] placeholder:text-paper-muted focus:border-[rgba(104,103,234,0.38)] focus:bg-white focus:outline-none focus:shadow-[0_0_0_5px_rgba(104,103,234,0.09)]"
          value={other}
          onChange={(e) => onOtherChange(e.target.value)}
          placeholder="e.g. Romantasy, Cli-fi, Court intrigue"
          aria-label="Other genre"
        />
      )}
    </div>
  );
}

