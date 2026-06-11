import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  api,
  type ChapterDetail,
  type ChapterStages,
  type ChapterSummary,
} from "../api/client";
import StatusPill from "../components/StatusPill";
import PipelineFlow, { type StageKey } from "../components/PipelineFlow";
import FinalEditor from "../components/FinalEditor";
import Inspector from "../components/Inspector";
import Breadcrumbs from "../components/Breadcrumbs";
import { useToast } from "../components/Toaster";
import { useRunPhase } from "../hooks/useRunPhase";

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
  const [busy, setBusy] = useState<null | "saving" | "promoting">(null);
  const [focus, setFocus] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [showBinder, setShowBinder] = useState(true);
  const [showInspector, setShowInspector] = useState(true);
  const navigate = useNavigate();

  // refs so the unmount/unload/autosave handlers see the latest values
  const dirtyRef = useRef(false);
  const textRef = useRef("");
  const busyRef = useRef<typeof busy>(null);
  dirtyRef.current = dirty;
  textRef.current = finalText;
  busyRef.current = busy;

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

  const reload = useCallback(() => {
    setError(null);
    api.chapter(id, num).then(setMeta).catch((e) => setError(String(e)));
    api.chapters(id).then(setSiblings).catch(() => setSiblings([]));
    api
      .stages(id, num)
      .then((s) => {
        setStages(s);
        // don't clobber an in-progress human edit when a job refreshes data
        if (!dirtyRef.current) {
          setFinalText(s.final ?? "");
          setDirty(false);
        }
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, num]);

  useEffect(() => {
    reload();
  }, [reload]);

  const { run, runningStage, isRunning } = useRunPhase(id, reload);

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

  // Debounced autosave — the dirty guard is just a backstop now.
  const saveRef = useRef<() => void>(() => {});
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      if (dirtyRef.current && busyRef.current == null) saveRef.current();
    }, 1500);
    return () => clearTimeout(t);
  }, [finalText, dirty]);

  // [ / ] jump between chapters (ignored while typing in an editor/field)
  useEffect(() => {
    const isTyping = () => {
      const el = document.activeElement as HTMLElement | null;
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
    };
    const onKey = (e: KeyboardEvent) => {
      if (isTyping() || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key !== "[" && e.key !== "]") return;
      const ordered = [...siblings].sort((a, b) => a.number - b.number);
      const idx = ordered.findIndex((c) => c.number === num);
      if (e.key === "[" && idx > 0) navigate(`/projects/${id}/chapters/${ordered[idx - 1].number}`);
      if (e.key === "]" && idx >= 0 && idx < ordered.length - 1)
        navigate(`/projects/${id}/chapters/${ordered[idx + 1].number}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [siblings, num, id, navigate]);

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load: {error}
        </div>
      </div>
    );
  if (!stages)
    return (
      <div className="mx-auto max-w-[760px] px-10 py-12">
        <div className="h-3.5 w-40 animate-pulse rounded bg-paper-card" />
        <div className="mt-4 h-8 w-1/2 animate-pulse rounded bg-paper-card" />
        <div className="mt-6 h-16 w-full animate-pulse rounded-lg bg-paper-card" />
        <div className="mt-8 h-[50vh] w-full animate-pulse rounded-md bg-paper-card" />
      </div>
    );

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
      setLastSaved("just now");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveRef.current = save;

  async function flush() {
    if (dirtyRef.current && busyRef.current == null) await save();
  }

  const canPromote = stages.revised != null || stages.draft != null;
  const promoteFrom = stages.revised != null ? "Revised" : "Draft";

  return (
    <div className="flex h-full">
      {/* Binder */}
      <nav className={`w-[210px] shrink-0 flex-col border-r border-paper-line bg-paper-card/40 ${showBinder && !focus ? "flex" : "hidden"}`}>
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
        {!focus && (
        <div className="border-b border-paper-line bg-paper-card/30 px-8 py-5">
          <div className="mx-auto max-w-[760px]">
            <Breadcrumbs items={[
              { label: "Library", to: "/" },
              { label: id.replace(/-/g, " "), to: `/projects/${id}` },
              { label: `Chapter ${num}` },
            ]} />
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
                {meta?.pov && <span>POV {meta.pov}</span>}
                <StatusPill status={stages.status} />
                <div className="flex overflow-hidden rounded-lg border border-paper-line">
                  <PanelToggle on={showBinder} onClick={() => setShowBinder((b) => !b)} label="Binder" />
                  <PanelToggle on={showInspector} onClick={() => setShowInspector((s) => !s)} label="Notes" border />
                </div>
              </div>
            </div>
            <PipelineFlow stages={stages} selected={selected} onSelect={selectStage} />

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <RunButton label="Generate Draft" running={runningStage === "write"}
                         disabled={isRunning} onClick={() => run("write", { number: num })} />
              <RunButton label="Revise" running={runningStage === "edit"}
                         disabled={isRunning || stages.draft == null}
                         onClick={() => run("edit", { number: num })} />
              <RunButton label="Validate" running={runningStage === "validate"}
                         disabled={isRunning || (stages.draft == null && stages.revised == null)}
                         onClick={() => run("validate", { number: num })} />
              <RunButton label="Approve" running={runningStage === "approve"}
                         disabled={isRunning} onClick={() => run("approve", { number: num })} />
              {isRunning && (
                <span className="ml-1 inline-flex items-center gap-2 text-[12px] text-ink-muted" aria-live="polite">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-amber-deep" />
                  Agent working…
                </span>
              )}
            </div>
          </div>
        </div>
        )}

        <div className={focus ? "px-6 py-8" : "px-8 py-10"}>
          <div className={`mx-auto ${selected === "final" ? "max-w-[960px]" : "max-w-[760px]"}`}>
            {selected === "final" ? (
              <FinalEditor
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
                lastSaved={lastSaved}
                focus={focus}
                onToggleFocus={() => setFocus((f) => !f)}
              />
            ) : (
              <ProvenancePane stage={selected} text={stages[selected]} />
            )}
          </div>
        </div>
      </div>

      {showInspector && !focus && (
        <Inspector
          id={id}
          num={num}
          currentText={finalText}
          flush={flush}
          onRestored={(text) => {
            setFinalText(text);
            setDirty(false);
            reload();
          }}
        />
      )}
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

function Empty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <p className="font-display text-[18px] text-ink-text">{title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{hint}</p>
    </div>
  );
}

function PanelToggle({ on, onClick, label, border }: {
  on: boolean; onClick: () => void; label: string; border?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      title={`Toggle ${label}`}
      className={`px-2.5 py-1 text-[12px] font-medium transition-colors ${border ? "border-l border-paper-line" : ""} ${
        on ? "bg-ink/[0.06] text-ink-text" : "text-ink-muted hover:bg-ink/5"
      }`}
    >
      {label}
    </button>
  );
}

function RunButton({
  label, onClick, running, disabled,
}: { label: string; onClick: () => void; running: boolean; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg border border-paper-line bg-paper-card px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
    >
      {running ? "Running…" : label}
    </button>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
