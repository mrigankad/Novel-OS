import { useEffect } from "react";
import { STUDIO_MODES } from "../lib/studioMode";
import { useStudioMode } from "../hooks/useStudioMode";

/**
 * Plan / Write / Revise (design spec §4.1).
 *
 * Deliberately three, deliberately always visible, deliberately keyboard-first
 * (⌘1/2/3): the mode a writer is in changes what the whole studio should be
 * showing them, and it changes several times an hour.
 */
export default function ModeSwitch({ className = "" }: { className?: string }) {
  const [mode, setMode] = useStudioMode();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return;
      const index = ["1", "2", "3"].indexOf(e.key);
      if (index === -1) return;
      e.preventDefault();
      setMode(STUDIO_MODES[index].id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setMode]);

  return (
    <div
      role="radiogroup"
      aria-label="Studio mode"
      className={`inline-flex items-center gap-0.5 rounded-xl bg-paper-line/50 p-0.5 ${className}`}
    >
      {STUDIO_MODES.map((m, i) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={mode === m.id}
          title={`${m.hint} (⌘${i + 1})`}
          onClick={() => setMode(m.id)}
          className={`rounded-lg px-2.5 py-1 text-[12.5px] font-medium transition ${
            mode === m.id
              ? "bg-white text-ink-text shadow-[0_1px_3px_rgba(48,62,98,0.12)]"
              : "text-ink-muted hover:text-ink-text"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
