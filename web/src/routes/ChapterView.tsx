import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  api,
  type ChapterDetail,
  type ChapterStages,
  type ChapterSummary,
} from "../api/client";
import StatusPill from "../components/StatusPill";
import PipelineFlow, { type StageKey } from "../components/PipelineFlow";
import { useToast } from "../components/Toaster";

const STAGE_KEYS: StageKey[] = ["outline", "draft", "revised", "final"];

function firstPresent(s: ChapterStages): StageKey {
  if (s.final != null) return "final";
  if (s.revised != null) return "revised";
  if (s.draft != null) return "draft";
  return "outline";
}

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const num = Number(n);
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [meta, setMeta] = useState<ChapterDetail | null>(null);
  const [stages, setStages] = useState<ChapterStages | null>(null);
  const [siblings, setSiblings] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [finalText, setFinalText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [busy, setBusy] = useState<null | "saving" | "promoting">(null);

  // refs so the unmount/unload handlers see the latest values
  const dirtyRef = useRef(false);
  const textRef = useRef("");
  dirtyRef.current = dirty;
  textRef.current = finalText;

  const stageParam = searchParams.get("stage") as StageKey | null;
  const selected: StageKey =
    stageParam && STAGE_KEYS.includes(stageParam)
      ? stageParam
      : stages
        ? firstPresent(stages)
        : "outline";

  function selectStage(s: StageKey) {
    setSearchParams(
      (prev) => {
        prev.set("stage", s);
        return prev;
      },
      { replace: true },
    );
  }

  useEffect(() => {
    setError(null);
    api.chapter(id, num).then(setMeta).catch((e) => setError(String(e)));
    api.chapters(id).then(setSiblings).catch(() => setSiblings([]));
    api
      .stages(id, num)
      .then((s) => {
        setStages(s);
        setFinalText(s.final ?? "");
        setDirty(false);
      })
      .catch((e) => setError(String(e)));
  }, [id, num]);

  // Warn on tab close / refresh with unsaved edits
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      // best-effort flush if navigating away mid-edit
      if (dirtyRef.current) api.saveFinal(id, num, textRef.current).catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, num]);

  const wordCount = useMemo(
    () => (finalText.trim() ? finalText.trim().split(/\s+/).length : 0),
    [finalText],
  );

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load: {error}
        </div>
      </div>
    );
  if (!stages) return <div className="px-10 py-12 text-ink-muted">Loading…</div>;

  async function promote() {
    setBusy("promoting");
    try {
      const r = await api.promoteFinal(id, num);
      setFinalText(r.final);
      setDirty(false);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      selectStage("final");
      toast("Promoted to Final", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy("saving");
    try {
      const r = await api.saveFinal(id, num, textRef.current);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      setDirty(false);
      toast("Saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  const canPromote = stages.revised != null || stages.draft != null;
  const promoteFrom = stages.revised != null ? "Revised" : "Draft";

  return (
    <div className="flex h-full">
      {/* Binder */}
      <nav className="hidden w-[210px] shrink-0 flex-col border-r border-paper-line bg-paper-card/40 lg:flex">
        <div className="px-5 pb-3 pt-6">
          <Link
            to={`/projects/${id}`}
            className="text-[12.5px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
          >
            ← {id.replace(/-/g, " ")}
          </Link>
        </div>
        <p className="px-5 pb-2 text-[10.5px] font-bold uppercase tracking-[0.16em] text-paper-muted">
          Binder
        </p>
        <div className="flex flex-col gap-0.5 px-2.5">
          {siblings.map((c) => (
            <Link
              key={c.number}
              to={`/projects/${id}/chapters/${c.number}`}
              className={`flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                c.number === num
                  ? "bg-amber/15 font-medium text-ink-text"
                  : "text-ink-muted hover:bg-ink/5"
              }`}
            >
              <span className="nums font-mono text-[11px] text-paper-muted">{c.number}</span>
              <span className="truncate">{c.title || "Untitled"}</span>
            </Link>
          ))}
        </div>
      </nav>

      {/* Pipeline editor */}
      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <div className="border-b border-paper-line bg-paper-card/30 px-8 py-5">
          <div className="mx-auto max-w-[760px]">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11.5px] font-semibold uppercase tracking-[0.16em] text-amber-deep">
                  Chapter {num}
                </p>
                <h1 className="font-display text-[24px] font-semibold tracking-tight text-ink-text text-balance">
                  {meta?.title || stages.status}
                </h1>
              </div>
              <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
                <StatusPill status={stages.status} />
                {meta?.pov && <span>POV {meta.pov}</span>}
              </div>
            </div>
            <PipelineFlow stages={stages} selected={selected} onSelect={selectStage} />
          </div>
        </div>

        <div className="px-8 py-10">
          <div className="mx-auto max-w-[760px]">
            {selected === "final" ? (
              <FinalPane
                hasFinal={stages.final != null}
                canPromote={canPromote}
                promoteFrom={promoteFrom}
                text={finalText}
                onChange={(v) => {
                  setFinalText(v);
                  setDirty(true);
                }}
                onSave={save}
                onPromote={promote}
                dirty={dirty}
                busy={busy}
                wordCount={wordCount}
                mode={mode}
                setMode={setMode}
              />
            ) : (
              <ProvenancePane stage={selected} text={stages[selected]} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ProvenancePane({ stage, text }: { stage: StageKey; text: string | null }) {
  if (text == null) {
    return (
      <Empty
        title={`${cap(stage)} not generated yet`}
        hint={
          stage === "outline"
            ? "The Architect plans the beats first."
            : "Run the pipeline to produce this stage."
        }
      />
    );
  }
  const outline = stage === "outline";
  return (
    <article className="rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <div className="mb-6 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-paper-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-st-approved" />
        Provenance · read-only — the reviewed Final is canonical
      </div>
      <div className={outline ? "prose-outline" : "prose-manuscript"}>
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
    </article>
  );
}

function FinalPane(props: {
  hasFinal: boolean;
  canPromote: boolean;
  promoteFrom: string;
  text: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onPromote: () => void;
  dirty: boolean;
  busy: null | "saving" | "promoting";
  wordCount: number;
  mode: "write" | "preview";
  setMode: (m: "write" | "preview") => void;
}) {
  const { hasFinal, canPromote, promoteFrom, text, onChange, onSave, onPromote,
    dirty, busy, wordCount, mode, setMode } = props;

  if (!hasFinal) {
    return (
      <div className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
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

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-deep">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-deep" />
          Final · {mode === "write" ? "editing" : "preview"}
        </div>
        <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
          <span className="nums">{wordCount.toLocaleString()} words</span>
          <span aria-live="polite" className="min-w-[64px] text-right">
            {busy === "saving" ? (
              <span className="text-paper-muted">Saving…</span>
            ) : dirty ? (
              <span className="text-amber-deep">● Unsaved</span>
            ) : (
              <span className="text-st-approved">● Saved</span>
            )}
          </span>
          {/* Write / Preview segmented control */}
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            {(["write", "preview"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1 text-[12.5px] font-medium capitalize transition-colors ${
                  mode === m ? "bg-ink text-on-ink" : "text-ink-muted hover:bg-ink/5"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <button
            onClick={onSave}
            disabled={!dirty || busy != null}
            className="rounded-lg bg-ink px-4 py-1.5 text-[13px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          >
            {busy === "saving" ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      {mode === "write" ? (
        <label className="block">
          <span className="sr-only">Final chapter text</span>
          <textarea
            value={text}
            onChange={(e) => onChange(e.target.value)}
            spellCheck
            className="prose-manuscript min-h-[60vh] w-full resize-y rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line"
          />
        </label>
      ) : (
        <article className="min-h-[60vh] rounded-md bg-paper-card px-11 py-12 shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
          <div className="prose-manuscript">
            <ReactMarkdown>{text || "*Nothing to preview yet.*"}</ReactMarkdown>
          </div>
        </article>
      )}
    </div>
  );
}

function Empty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <p className="font-display text-[18px] text-ink-text">{title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{hint}</p>
    </div>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
