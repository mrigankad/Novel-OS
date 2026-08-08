import { useCallback, useRef, useState } from "react";
import RichTextEditor, { type CommentAnchor } from "./RichTextEditor";
import {
  EMPTY_DOC,
  insertImage,
  insertSceneBreak,
  setHeading,
  toggleBlockquote,
  toggleBold,
  toggleItalic,
  type EditorHandle,
  type PMDoc,
} from "../lib/richText";
import { api, type CodexEntry } from "../api/client";
import { READER_FONTS, getReaderFont, setReaderFont, type ReaderFont } from "../theme";
import ChoiceGroup from "./ChoiceGroup";
import ContextMenu, { type ContextMenuItem } from "./ContextMenu";
import LinkCodexModal from "./LinkCodexModal";
import EntityPopover from "./EntityPopover";
import ConsequencePreviewModal from "./ConsequencePreview";
import { type ConsequencePreview as ConsequencePreviewPayload } from "../api/client";

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

function countWords(text: string) {
  const t = text.trim();
  return t ? t.split(/\s+/).length : 0;
}

export default function FinalEditor(props: {
  projectId: string;
  chapterNumber: number;
  hasFinal: boolean;
  canPromote: boolean;
  promoteFrom: string;
  doc: PMDoc;
  wordCount?: number;
  onChange: (doc: PMDoc) => void;
  onSave: () => void;
  onPromote: () => void;
  dirty: boolean;
  busy: null | "saving" | "promoting";
  lastSaved: string | null;
  focus: boolean;
  onToggleFocus: () => void;
  onCommentSelection?: (sel: { from: number; to: number; quote: string }) => void;
  commentAnchors?: CommentAnchor[];
}) {
  const {
    projectId, chapterNumber, hasFinal, canPromote, promoteFrom, doc, wordCount, onChange, onSave, onPromote,
    dirty, busy, lastSaved, focus, onToggleFocus, onCommentSelection, commentAnchors = [],
  } = props;

  const handleRef = useRef<EditorHandle | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [sizeIdx, setSizeIdx] = usePersisted("novelos-editor-size", 1);
  const [measure, setMeasure] = usePersisted<Measure>("novelos-editor-measure", "normal");
  const [readerFont, setReaderFontState] = useState<ReaderFont>(getReaderFont);
  const [uploading, setUploading] = useState(false);
  const [liveWords, setLiveWords] = useState(wordCount ?? 0);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkMode, setLinkMode] = useState<"link" | "create">("link");
  const [seedName, setSeedName] = useState("");
  const [ctx, setCtx] = useState<{ x: number; y: number; items: ContextMenuItem[] } | null>(null);
  const [entity, setEntity] = useState<{ x: number; y: number; entry: CodexEntry } | null>(null);
  const [rewriteOpen, setRewriteOpen] = useState(false);
  const [rewriteSel, setRewriteSel] = useState<{
    from: number; to: number; quote: string; before: string; after: string;
  } | null>(null);
  const chooseFont = (f: ReaderFont) => { setReaderFont(f); setReaderFontState(f); };

  function openRewrite() {
    const sel = handleRef.current?.getSelection();
    if (!sel) return;
    setRewriteSel(sel);
    setRewriteOpen(true);
  }

  async function acceptRewrite(preview: ConsequencePreviewPayload) {
    const ed = handleRef.current?.editor;
    if (!ed || !rewriteSel) throw new Error("Editor selection lost.");
    ed.chain()
      .focus()
      .setTextSelection({ from: rewriteSel.from, to: rewriteSel.to })
      .insertContent(preview.rewritten)
      .run();
    const nextDoc = ed.getJSON() as PMDoc;
    handleChange(nextDoc);
    const result = await api.acceptConsequence(projectId, chapterNumber, {
      preview_id: preview.preview_id,
      rewritten: preview.rewritten,
      doc: nextDoc,
      state_delta: preview.state_delta,
    });
    handleChange(result.final.doc as PMDoc);
  }

  function openActionMenu(x: number, y: number) {
    if (mode !== "write") return;
    const sel = handleRef.current?.getSelection();
    setCtx({
      x,
      y,
      items: [
        {
          id: "rewrite",
          label: "Rewrite with AI",
          disabled: !sel,
          onSelect: () => openRewrite(),
        },
        {
          id: "ask",
          label: "Ask Scribe…",
          disabled: false,
          onSelect: () => {
            document.getElementById("scribe-chat-input")?.focus();
          },
        },
        {
          id: "comment",
          label: "Comment",
          disabled: !sel,
          onSelect: () => { if (sel) onCommentSelection?.(sel); },
        },
        {
          id: "link",
          label: "Link to Codex",
          disabled: !sel,
          onSelect: () => openLink("link"),
        },
        {
          id: "create",
          label: "Create Codex entry",
          disabled: !sel,
          onSelect: () => openLink("create"),
        },
      ],
    });
  }

  const size = SIZES[Math.max(0, Math.min(SIZES.length - 1, sizeIdx))];
  const words = liveWords;

  const onReady = useCallback((h: EditorHandle) => {
    handleRef.current = h;
    setLiveWords(countWords(h.getText()));
  }, []);

  function handleChange(next: PMDoc) {
    onChange(next);
    setLiveWords(countWords(handleRef.current?.getText() ?? ""));
  }

  function openLink(nextMode: "link" | "create") {
    const sel = handleRef.current?.getSelection();
    setSeedName(sel?.quote.trim() || "");
    setLinkMode(nextMode);
    setLinkOpen(true);
  }

  function applyMention(entry: CodexEntry) {
    handleRef.current?.setCodexMention(entry.id, entry.entry_type);
  }

  async function pickImage(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    try {
      const item = await api.uploadMedia(projectId, file, "inline", file.name);
      insertImage(handleRef.current, api.mediaUrl(item), item.alt || file.name);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (!hasFinal) {
    return (
      <div className="manuscript-page mx-auto max-w-[680px] px-11 py-14 text-center">
        <p className="font-display text-[20px] text-ink-text">No Final yet</p>
        <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-ink-muted">
          The Final is the human-reviewed, canonical chapter. Promote the latest AI stage to
          start reviewing your drafts stay untouched as provenance.
        </p>
        <button
          type="button"
          onClick={onPromote}
          disabled={!canPromote || busy != null}
          className="btn-primary mt-6 disabled:opacity-40"
        >
          {busy === "promoting" ? "Promoting…" : canPromote ? `Promote ${promoteFrom} → Final` : "Nothing to Promote Yet"}
        </button>
      </div>
    );
  }

  return (
    <div style={{ ["--editor-size" as string]: `${size}rem` }} className="mx-auto">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-ink" />
            Final · {mode === "write" ? "Editing" : "Preview"}
          </span>
          <button type="button" onClick={onToggleFocus} className="btn-ghost" title="Focus mode">
            {focus ? "Exit focus" : "Focus"}
          </button>
        </div>

        <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
          <span className="nums">{words.toLocaleString()} words</span>
          <span aria-live="polite" className="min-w-[78px] text-right">
            {busy === "saving" ? <span className="text-paper-muted">Saving…</span>
              : dirty ? <span className="text-ink-muted">● Unsaved</span>
              : <span className="text-st-approved">● {lastSaved ? `Saved ${lastSaved}` : "Saved"}</span>}
          </span>

          <div className="flex items-center overflow-hidden rounded-full border border-paper-line bg-[var(--color-surface-warm)]">
            <button type="button" onClick={() => setSizeIdx(Math.max(0, sizeIdx - 1))}
                    className="px-2.5 py-1 text-ink-muted hover:text-ink" aria-label="Smaller text">A−</button>
            <button type="button" onClick={() => setSizeIdx(Math.min(SIZES.length - 1, sizeIdx + 1))}
                    className="border-l border-paper-line px-2.5 py-1 text-ink-muted hover:text-ink" aria-label="Larger text">A+</button>
            <button type="button" onClick={() => setMeasure(measure === "wide" ? "narrow" : measure === "narrow" ? "normal" : "wide")}
                    className="border-l border-paper-line px-2.5 py-1 text-[11px] font-medium tracking-[-0.01em] text-ink-muted hover:text-ink"
                    title="Reading width">{measure}</button>
            <div className="border-l border-paper-line pl-1">
              <ChoiceGroup
                label="Reading font"
                variant="segmented"
                size="sm"
                value={readerFont}
                onChange={(v) => chooseFont(v)}
                options={READER_FONTS.map((f) => ({
                  value: f.value,
                  label: f.label,
                  preview: (
                    <span
                      style={{
                        fontFamily:
                          f.value === "serif"
                            ? "var(--font-reader-serif)"
                            : f.value === "mono"
                              ? "var(--font-reader-mono)"
                              : "var(--font-reader-sans)",
                      }}
                    >
                      Aa
                    </span>
                  ),
                }))}
              />
            </div>
          </div>

          <div className="flex overflow-hidden rounded-full border border-paper-line bg-[var(--color-surface-warm)] p-0.5">
            {(["write", "preview"] as const).map((m) => (
              <button key={m} type="button" onClick={() => setMode(m)}
                      className={`rounded-full px-3 py-1 text-[12.5px] font-medium capitalize transition-colors ${
                        mode === m ? "bg-ink text-on-ink" : "text-ink-muted hover:text-ink"}`}>
                {m}
              </button>
            ))}
          </div>
          <button type="button" onClick={onSave} disabled={!dirty || busy != null}
                  className="btn-primary disabled:opacity-40">
            {busy === "saving" ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {mode === "write" && (
        <div className="mb-2 flex items-center gap-1" style={{ maxWidth: MEASURES[measure], marginInline: "auto" }}>
          <TBtn onClick={() => toggleBold(handleRef.current)} label="Bold"><b>B</b></TBtn>
          <TBtn onClick={() => toggleItalic(handleRef.current)} label="Italic"><i>I</i></TBtn>
          <TBtn onClick={() => setHeading(handleRef.current, 2)} label="Heading">H</TBtn>
          <TBtn onClick={() => toggleBlockquote(handleRef.current)} label="Quote">”</TBtn>
          <TBtn onClick={() => insertSceneBreak(handleRef.current)} label="Scene break">✦</TBtn>
          <div className="mx-1 h-5 w-px bg-paper-line" />
          <TBtn onClick={() => fileRef.current?.click()} label="Insert image">
            {uploading ? "…" : "▣"}
          </TBtn>
          <TBtn
            onClick={() => {
              const sel = handleRef.current?.getSelection();
              if (sel) onCommentSelection?.(sel);
            }}
            label="Comment on selection"
          >
            ¶
          </TBtn>
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
            onChange={(e) => void pickImage(e.target.files?.[0])}
          />
        </div>
      )}

      <article
        className="manuscript-page px-11 py-12"
        style={{ maxWidth: MEASURES[measure], marginInline: "auto" }}
      >
        <div className="prose-manuscript" style={{ fontSize: `${size}rem` }}>
          <RichTextEditor
            doc={doc?.type === "doc" ? doc : EMPTY_DOC}
            onChange={handleChange}
            onReady={onReady}
            editable={mode === "write"}
            commentAnchors={commentAnchors}
            onContextMenu={(e) => {
              e.preventDefault();
              openActionMenu(e.clientX, e.clientY);
            }}
            onSelectionAction={(x, y) => openActionMenu(x, y)}
            onMentionClick={async (entryId, entryType, x, y) => {
              try {
                const list = await api.codex(projectId, entryType);
                const found = list.find((e) => e.id === entryId) ?? null;
                if (found) setEntity({ x, y, entry: found });
              } catch {
                /* ignore */
              }
            }}
          />
        </div>
      </article>

      <ContextMenu
        open={ctx != null}
        x={ctx?.x ?? 0}
        y={ctx?.y ?? 0}
        items={ctx?.items ?? []}
        onClose={() => setCtx(null)}
      />

      <ConsequencePreviewModal
        open={rewriteOpen && rewriteSel != null}
        onClose={() => { setRewriteOpen(false); setRewriteSel(null); }}
        projectId={projectId}
        chapter={chapterNumber}
        selection={rewriteSel?.quote ?? ""}
        beforeContext={rewriteSel?.before ?? ""}
        afterContext={rewriteSel?.after ?? ""}
        onAccept={acceptRewrite}
      />

      <LinkCodexModal
        projectId={projectId}
        open={linkOpen}
        mode={linkMode}
        seedName={seedName}
        onClose={() => setLinkOpen(false)}
        onLinked={applyMention}
      />

      <EntityPopover
        open={entity != null}
        x={entity?.x ?? 0}
        y={entity?.y ?? 0}
        entry={entity?.entry ?? null}
        projectId={projectId}
        onClose={() => setEntity(null)}
      />
    </div>
  );
}

function TBtn({ children, onClick, label }: { children: React.ReactNode; onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick} title={label} aria-label={label}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-paper-line bg-paper-card text-[14px] text-ink-text transition-colors hover:bg-[var(--color-surface-warm)]">
      {children}
    </button>
  );
}
