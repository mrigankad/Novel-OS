import { useState } from "react";
import {
  api,
  type ConsequencePreview as Preview,
  type ContinuityFinding,
} from "../api/client";
import Modal, { Field, fieldClass } from "./Modal";
import Icon from "./Icon";
import { useToast } from "./toastContext";

/** P3.1: rewrite a span, show deterministic + predicted ripple, accept into Final. */
export default function ConsequencePreviewModal({
  open,
  onClose,
  projectId,
  chapter,
  selection,
  beforeContext,
  afterContext,
  onAccept,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapter: number;
  selection: string;
  beforeContext: string;
  afterContext: string;
  /** Parent replaces selection in TipTap, then persists via accept API. */
  onAccept: (preview: Preview) => Promise<void>;
}) {
  const toast = useToast();
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);

  // Reset the form each time the dialog opens on a fresh selection. Adjusting
  // during render rather than in an effect avoids a flash of the previous
  // preview - see react.dev "You Might Not Need an Effect".
  const session = open ? selection : null;
  const [lastSession, setLastSession] = useState(session);
  if (session !== lastSession) {
    setLastSession(session);
    if (open) {
      setInstruction("");
      setPreview(null);
      setBusy(false);
      setAccepting(false);
    }
  }

  async function runPreview(e?: React.FormEvent) {
    e?.preventDefault();
    const inst = instruction.trim();
    if (!inst || busy) return;
    setBusy(true);
    setPreview(null);
    try {
      const result = await api.previewConsequence(projectId, chapter, {
        selection,
        instruction: inst,
        before_context: beforeContext,
        after_context: afterContext,
      });
      setPreview(result);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    if (!preview || accepting) return;
    setAccepting(true);
    try {
      await onAccept(preview);
      toast("Rewrite applied to Final", "success");
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setAccepting(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Rewrite with consequence preview">
      <p className="mb-4 text-[13px] leading-relaxed text-ink-muted">
        The Scribe rewrites your selection. Continuity checks show hard ripple;
        AI guesses are labeled predicted - never treated as fact.
      </p>

      <div className="mb-4 rounded-2xl border border-[rgba(74,91,133,0.12)] bg-white/60 px-3.5 py-3">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Selection
        </p>
        <p className="max-h-28 overflow-y-auto whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-text">
          {selection}
        </p>
      </div>

      {!preview && (
        <form onSubmit={runPreview}>
          <Field label="What should change?">
            <textarea
              className={fieldClass}
              rows={3}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="e.g. Soften the accusation - she suspects but does not accuse yet"
              disabled={busy}
            />
          </Field>
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !instruction.trim()}
              className="btn-primary disabled:opacity-40"
            >
              {busy ? "Rewriting…" : "Preview ripple"}
            </button>
          </div>
        </form>
      )}

      {preview && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-[rgba(104,103,234,0.22)] bg-[rgba(104,103,234,0.06)] px-3.5 py-3">
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-violet)]">
              <Icon name="sparkles" className="h-3.5 w-3.5" />
              Rewritten
            </p>
            <p className="max-h-36 overflow-y-auto whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-text">
              {preview.rewritten}
            </p>
          </div>

          <RippleList
            title="Deterministic ripple"
            hint="From continuity checks after a dry world-state apply"
            findings={preview.deterministic}
            empty="No new continuity findings."
          />

          <div>
            <p className="mb-1.5 text-[12px] font-semibold text-ink-text">
              Predicted
              <span className="ml-2 font-normal text-ink-muted">(AI guess - not fact)</span>
            </p>
            {preview.predicted.length === 0 ? (
              <p className="text-[13px] text-ink-muted">No predicted consequences.</p>
            ) : (
              <ul className="space-y-1.5">
                {preview.predicted.map((p, i) => (
                  <li
                    key={i}
                    className="rounded-xl border border-dashed border-[rgba(74,91,133,0.18)] bg-white/50 px-3 py-2 text-[13px] text-ink-text"
                  >
                    {p.message}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {preview.changelog.length > 0 && (
            <div>
              <p className="mb-1.5 text-[12px] font-semibold text-ink-text">World-state delta</p>
              <ul className="space-y-1 text-[12.5px] text-ink-muted">
                {preview.changelog.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap justify-end gap-2 pt-1">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setPreview(null)}
              disabled={accepting}
            >
              Tweak
            </button>
            <button type="button" className="btn-ghost" onClick={onClose} disabled={accepting}>
              Discard
            </button>
            <button
              type="button"
              className="btn-primary disabled:opacity-40"
              disabled={accepting}
              onClick={() => void accept()}
            >
              {accepting ? "Applying…" : "Accept into Final"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function RippleList({
  title, hint, findings, empty,
}: {
  title: string;
  hint: string;
  findings: ContinuityFinding[];
  empty: string;
}) {
  return (
    <div>
      <p className="mb-0.5 flex items-center gap-1.5 text-[12px] font-semibold text-ink-text">
        <Icon name="waypoints" className="h-3.5 w-3.5 text-[var(--color-violet)]" />
        {title}
      </p>
      <p className="mb-1.5 text-[11.5px] text-ink-muted">{hint}</p>
      {findings.length === 0 ? (
        <p className="text-[13px] text-ink-muted">{empty}</p>
      ) : (
        <ul className="space-y-1.5">
          {findings.map((f, i) => (
            <li
              key={i}
              className="rounded-xl border border-[rgba(74,91,133,0.12)] bg-white/70 px-3 py-2 text-[13px]"
            >
              <span className="mr-2 text-[11px] font-semibold uppercase text-ink-muted">
                {f.severity}
              </span>
              {f.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
