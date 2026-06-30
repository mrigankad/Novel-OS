import type { ReactNode } from "react";

export function formatSavedAt(d = new Date()): string {
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** Visible save state: Saving… / Unsaved / Saved at time */
export function SaveStatus({
  dirty,
  saving,
  lastSaved,
  className = "",
}: {
  dirty: boolean;
  saving: boolean;
  lastSaved: string | null;
  className?: string;
}) {
  return (
    <span
      aria-live="polite"
      className={`inline-flex min-w-[5.5rem] items-center gap-1.5 text-[12.5px] ${className}`}
    >
      {saving ? (
        <>
          <span className="h-2 w-2 animate-pulse rounded-full bg-paper-muted" />
          <span className="text-ink-muted">Saving…</span>
        </>
      ) : dirty ? (
        <>
          <span className="h-2 w-2 rounded-full bg-amber-deep" />
          <span className="font-medium text-amber-deep">Unsaved changes</span>
        </>
      ) : (
        <>
          <span className="h-2 w-2 rounded-full bg-st-approved" />
          <span className="text-st-approved">
            {lastSaved ? `Saved ${lastSaved}` : "Saved"}
          </span>
        </>
      )}
    </span>
  );
}

export default function EditorSaveBar({
  label = "Save",
  dirty,
  saving,
  lastSaved,
  onSave,
  hint,
  autosaveNote = true,
  autosaveOnly = false,
}: {
  label?: string;
  dirty: boolean;
  saving: boolean;
  lastSaved: string | null;
  onSave?: () => void;
  hint?: ReactNode;
  autosaveNote?: boolean;
  /** Hide manual save button — status + autosave debounce only */
  autosaveOnly?: boolean;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-paper-line/80 bg-paper-card/60 px-3 py-2">
      <div className="flex flex-wrap items-center gap-3">
        {!autosaveOnly && onSave && (
          <button
            type="button"
            onClick={onSave}
            disabled={saving || !dirty}
            className="rounded-lg bg-ink px-4 py-1.5 text-[13px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          >
            {saving ? "Saving…" : label}
          </button>
        )}
        <SaveStatus dirty={dirty} saving={saving} lastSaved={lastSaved} />
        {(autosaveNote || autosaveOnly) && (
          <span className="hidden text-[11px] text-ink-muted sm:inline">
            Autosaves after you stop typing
          </span>
        )}
      </div>
      {hint ? (
        <span className="max-w-md text-[12px] leading-snug text-ink-muted">{hint}</span>
      ) : null}
    </div>
  );
}
