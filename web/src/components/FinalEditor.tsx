import { useRef, useState } from "react";
import { type EditorView, type ReactCodeMirrorRef } from "@uiw/react-codemirror";
import ReactMarkdown from "react-markdown";
import { openSearchPanel } from "@codemirror/search";
import MarkdownEditor from "./MarkdownEditor";
import { surround, prefixLine, insertBlock } from "./editorCommands";

const SIZES = [0.95, 1.075, 1.2, 1.35];
const MEASURES: Record<string, string> = { narrow: "34rem", normal: "42rem", wide: "52rem" };
type Measure = keyof typeof MEASURES;

function usePersisted<T>(key: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    const raw = localStorage.getItem(key);
    return raw != null ? (JSON.parse(raw) as T) : initial;
  });
  return [v, (nv: T) => { setV(nv); localStorage.setItem(key, JSON.stringify(nv)); }];
}

export default function FinalEditor(props: {
  hasFinal: boolean;
  canPromote: boolean;
  promoteFrom: string;
  text: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onPromote: () => void;
  dirty: boolean;
  busy: null | "saving" | "promoting";
  lastSaved: string | null;
  focus: boolean;
  onToggleFocus: () => void;
}) {
  const {
    hasFinal, canPromote, promoteFrom, text, onChange, onSave, onPromote,
    dirty, busy, lastSaved, focus, onToggleFocus,
  } = props;

  const cm = useRef<ReactCodeMirrorRef>(null);
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [sizeIdx, setSizeIdx] = usePersisted("novelos-editor-size", 1);
  const [measure, setMeasure] = usePersisted<Measure>("novelos-editor-measure", "normal");

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const size = SIZES[Math.max(0, Math.min(SIZES.length - 1, sizeIdx))];

  if (!hasFinal) {
    return (
      <div className="mx-auto max-w-[680px] rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
        <p className="font-display text-[20px] text-ink-text">No Final yet</p>
        <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-ink-muted">
          The Final is the human-reviewed, canonical chapter. Promote the latest AI stage to
          start reviewing — your drafts stay untouched as provenance.
        </p>
        <button
          onClick={onPromote}
          disabled={!canPromote || busy != null}
          className="mt-6 inline-flex items-center rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
        >
          {busy === "promoting" ? "Promoting…" : canPromote ? `Promote ${promoteFrom} → Final` : "Nothing to Promote Yet"}
        </button>
      </div>
    );
  }

  function cmd(fn: (v: EditorView) => void) {
    const view = cm.current?.view;
    if (view) fn(view);
  }

  return (
    <div style={{ ["--editor-size" as string]: `${size}rem` }} className="mx-auto" >
      {/* Control bar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-deep">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-deep" />
            Final · {mode === "write" ? "editing" : "preview"}
          </span>
          <button
            onClick={onToggleFocus}
            className="rounded-md px-2 py-1 text-[12px] font-medium text-ink-muted transition-colors hover:bg-ink/5"
            title="Focus mode"
          >
            {focus ? "Exit focus" : "Focus"}
          </button>
        </div>

        <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
          <span className="nums">{words.toLocaleString()} words</span>
          <span aria-live="polite" className="min-w-[78px] text-right">
            {busy === "saving" ? <span className="text-paper-muted">Saving…</span>
              : dirty ? <span className="text-amber-deep">● Unsaved</span>
              : <span className="text-st-approved">● {lastSaved ? `Saved ${lastSaved}` : "Saved"}</span>}
          </span>

          {/* Reading controls */}
          <div className="flex items-center overflow-hidden rounded-lg border border-paper-line">
            <button onClick={() => setSizeIdx(Math.max(0, sizeIdx - 1))}
                    className="px-2 py-1 text-ink-muted hover:bg-ink/5" aria-label="Smaller text">A−</button>
            <button onClick={() => setSizeIdx(Math.min(SIZES.length - 1, sizeIdx + 1))}
                    className="border-l border-paper-line px-2 py-1 text-ink-muted hover:bg-ink/5" aria-label="Larger text">A+</button>
            <button onClick={() => setMeasure(measure === "wide" ? "narrow" : measure === "narrow" ? "normal" : "wide")}
                    className="border-l border-paper-line px-2.5 py-1 text-[11px] font-semibold uppercase text-ink-muted hover:bg-ink/5"
                    title="Reading width">{measure}</button>
          </div>

          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            {(["write", "preview"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)}
                      className={`px-3 py-1 text-[12.5px] font-medium capitalize transition-colors ${
                        mode === m ? "bg-ink text-on-ink" : "text-ink-muted hover:bg-ink/5"}`}>
                {m}
              </button>
            ))}
          </div>
          <button onClick={onSave} disabled={!dirty || busy != null}
                  className="rounded-lg bg-ink px-4 py-1.5 text-[13px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
            {busy === "saving" ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {/* Formatting toolbar (write mode) */}
      {mode === "write" && (
        <div className="mb-2 flex items-center gap-1" style={{ maxWidth: MEASURES[measure], marginInline: "auto" }}>
          <TBtn onClick={() => cmd((v) => surround(v, "**"))} label="Bold"><b>B</b></TBtn>
          <TBtn onClick={() => cmd((v) => surround(v, "*"))} label="Italic"><i>I</i></TBtn>
          <TBtn onClick={() => cmd((v) => prefixLine(v, "## "))} label="Heading">H</TBtn>
          <TBtn onClick={() => cmd((v) => prefixLine(v, "> "))} label="Quote">”</TBtn>
          <TBtn onClick={() => cmd((v) => insertBlock(v, "\n\n---\n\n"))} label="Scene break">✦</TBtn>
          <div className="mx-1 h-5 w-px bg-paper-line" />
          <TBtn onClick={() => cmd((v) => openSearchPanel(v))} label="Find & replace">⌕</TBtn>
        </div>
      )}

      {/* Page */}
      <article className="rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line"
               style={{ maxWidth: MEASURES[measure], marginInline: "auto" }}>
        {mode === "write" ? (
          <div className="prose-manuscript">
            <MarkdownEditor ref={cm} value={text} onChange={onChange} placeholder="Write the chapter…" />
          </div>
        ) : (
          <div className="prose-manuscript" style={{ fontSize: `${size}rem` }}>
            <ReactMarkdown>{text || "*Nothing to preview yet.*"}</ReactMarkdown>
          </div>
        )}
      </article>
    </div>
  );
}

function TBtn({ children, onClick, label }: { children: React.ReactNode; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} title={label} aria-label={label}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-paper-line bg-paper-card text-[14px] text-ink-text transition-colors hover:bg-ink/5">
      {children}
    </button>
  );
}
