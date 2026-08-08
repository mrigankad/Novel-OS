import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { AnimatePresence, motion } from "motion/react";
import {
  api,
  type ChapterDetail,
  type ChapterStages,
  type ChapterSummary,
  type CommentItem,
} from "../api/client";
import StatusPill from "../components/StatusPill";
import PipelineFlow, { type StageKey } from "../components/PipelineFlow";
import FinalEditor from "../components/FinalEditor";
import ContinueChat from "../components/ContinueChat";
import Inspector, { type Tab as InspectorTab } from "../components/Inspector";
import BinderNav from "../components/BinderNav";
import Breadcrumbs from "../components/Breadcrumbs";
import Scene from "../components/Scene";
import { useToast } from "../components/toastContext";
import { useRunPhase } from "../hooks/useRunPhase";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { useLatestRef } from "../hooks/useLatestRef";
import { useStudioMode } from "../hooks/useStudioMode";
import { chapterLayoutFor, getStudioMode } from "../lib/studioMode";
import ModeSwitch from "../components/ModeSwitch";
import QuickCapture from "../components/QuickCapture";
import type { CommentAnchor } from "../components/RichTextEditor";
import { EMPTY_DOC, type PMDoc } from "../lib/richText";

/** Below this width, Binder + Notes steal too much manuscript space. */
const COMPACT_CHAPTER = "(max-width: 1100px)";

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

  const [finalDoc, setFinalDoc] = useState<PMDoc>(EMPTY_DOC);
  const [finalMarkdown, setFinalMarkdown] = useState("");
  const [finalWordCount, setFinalWordCount] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<null | "saving" | "promoting">(null);
  const [focus, setFocus] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const compact = useMediaQuery(COMPACT_CHAPTER);
  const [showBinder, setShowBinder] = useState(() =>
    typeof window !== "undefined" ? !window.matchMedia(COMPACT_CHAPTER).matches : true,
  );
  const [showInspector, setShowInspector] = useState(() =>
    typeof window !== "undefined" ? !window.matchMedia(COMPACT_CHAPTER).matches : true,
  );

  // When the viewport needs the space, collapse both rails. Adjusted during
  // render so a resize never paints an overflowing three-column frame.
  const [lastCompact, setLastCompact] = useState(compact);
  if (compact !== lastCompact) {
    setLastCompact(compact);
    if (compact) {
      setShowBinder(false);
      setShowInspector(false);
    }
  }

  const [inspectorTab, setInspectorTab] = useState<InspectorTab>(
    () => chapterLayoutFor(getStudioMode()).inspectorTab,
  );

  // Switching mode re-lays out the surface: Write clears the rails so the
  // manuscript is the page, Revise opens the Inspector on continuity. Applied
  // on change only, so a writer who then toggles a rail by hand keeps it.
  const [mode] = useStudioMode();
  const [lastMode, setLastMode] = useState(mode);
  if (mode !== lastMode) {
    setLastMode(mode);
    const layout = chapterLayoutFor(mode);
    setShowBinder(layout.binder && !compact);
    setShowInspector(layout.inspector && !compact);
    setInspectorTab(layout.inspectorTab);
  }
  const [pendingComment, setPendingComment] = useState<{
    from: number; to: number; quote: string;
  } | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);

  const commentAnchors: CommentAnchor[] = useMemo(
    () =>
      comments
        .filter((c) => !c.resolved && c.from_pos != null && c.to_pos != null)
        .map((c) => ({
          id: c.id,
          from: c.from_pos!,
          to: c.to_pos!,
          status: c.anchor_status,
        })),
    [comments],
  );

  useEffect(() => {
    api.comments(id, num).then(setComments).catch(() => setComments([]));
  }, [id, num]);

  const navigate = useNavigate();

  const dirtyRef = useLatestRef(dirty);
  const docRef = useLatestRef(finalDoc);
  const busyRef = useLatestRef(busy);

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

  const loadFinalDoc = useCallback(async () => {
    try {
      const body = await api.getFinalDoc(id, num);
      if (!dirtyRef.current) {
        setFinalDoc(body.doc as PMDoc);
        setFinalMarkdown(body.markdown);
        setFinalWordCount(body.word_count);
        setDirty(false);
      }
    } catch {
      /* no final yet leave empty */
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [id, num]);

  /** Seed Final from draft/revised so the author always has an editable surface. */
  const ensureFinal = useCallback(async (): Promise<ChapterStages | null> => {
    try {
      let next = await api.stages(id, num);
      if (next.final == null && (next.draft != null || next.revised != null)) {
        await api.promoteFinal(id, num, true);
        next = await api.stages(id, num);
      }
      setStages(next);
      if (next.final != null) await loadFinalDoc();
      else {
        toast("Nothing to edit yet — generate a draft first.", "error");
        return null;
      }
      return next;
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      return null;
    }
  }, [id, num, loadFinalDoc, toast]);

  const reload = useCallback(() => {
    // The banner clears on a successful refetch rather than optimistically at
    // call time, which would be a synchronous write from the mount effect.
    api.chapter(id, num)
      .then((m) => { setMeta(m); setError(null); })
      .catch((e) => setError(String(e)));
    api.chapters(id).then(setSiblings).catch(() => setSiblings([]));
    api
      .stages(id, num)
      .then(async (s) => {
        let next = s;
        // Auto-seed Final so opening a chapter lands on an editable manuscript
        // (draft/revised stay immutable provenance).
        if (s.final == null && (s.draft != null || s.revised != null)) {
          try {
            await api.promoteFinal(id, num, true);
            next = await api.stages(id, num);
          } catch {
            /* leave stages as-is; Edit CTA still available */
          }
        }
        setStages(next);
        if (next.final != null && !dirtyRef.current) {
          void loadFinalDoc();
        }
        // Prefer Final when no explicit stage is in the URL
        setSearchParams(
          (prev) => {
            if (prev.get("stage") || next.final == null) return prev;
            prev.set("stage", "final");
            return prev;
          },
          { replace: true },
        );
      })
      .catch((e) => setError(String(e)));
  // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [id, num, loadFinalDoc, setSearchParams]);

  useEffect(() => {
    reload();
  }, [reload]);

  const { run, runningStage, isRunning } = useRunPhase(id, reload);

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
      // Reading the refs at cleanup time is the point: this is the last-chance
      // flush, so it must see the newest doc, not the one captured at setup.
      /* eslint-disable react-hooks/exhaustive-deps */
      if (dirtyRef.current) {
        api.saveFinalDoc(id, num, docRef.current).catch(() => {});
      }
      /* eslint-enable react-hooks/exhaustive-deps */
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [id, num]);

  // `save` is a hoisted function declaration further down this component.
  const saveRef = useLatestRef(save);
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      if (dirtyRef.current && busyRef.current == null) saveRef.current();
    }, 1500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [finalDoc, dirty]);

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
        <div className="border border-ink bg-paper-card px-4 py-3 text-[13px] text-ink-text">
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
      // Author override from Final: force seeds even if Accept hasn't run yet.
      const r = await api.promoteFinal(id, num, true);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      const body = await api.getFinalDoc(id, num);
      setFinalDoc(body.doc as PMDoc);
      setFinalMarkdown(body.markdown);
      setFinalWordCount(body.word_count);
      setDirty(false);
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
      const r = await api.saveFinalDoc(id, num, docRef.current);
      setFinalMarkdown(r.markdown);
      setFinalWordCount(r.word_count);
      setStages((s) => (s ? { ...s, final: r.markdown } : s));
      setDirty(false);
      setLastSaved("just now");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function flush() {
    if (dirtyRef.current && busyRef.current == null) await save();
  }

  const canPromote = stages.revised != null || stages.draft != null;
  const promoteFrom = stages.revised != null ? "Revised" : "Draft";

  return (
    <Scene quiet className="h-full">
    <div className="flex h-full">
      <nav className={`glass-rail w-[210px] shrink-0 flex-col ${showBinder && !focus ? "flex" : "hidden"}`}>
        <div className="px-5 pb-3 pt-6">
          <Link
            to={`/projects/${id}`}
            className="text-[12.5px] font-medium text-ink-muted transition-colors hover:text-[var(--color-violet)]"
          >
            ← {id.replace(/-/g, " ")}
          </Link>
        </div>
        <p className="px-5 pb-2 text-[12px] font-medium tracking-[-0.01em] text-paper-muted">
          Binder
        </p>
        <div className="flex flex-col gap-0.5 px-2.5 pb-3">
          <Link
            to={`/projects/${id}`}
            className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:bg-white/45"
          >
            Dashboard
          </Link>
          <Link
            to={`/projects/${id}/chart`}
            className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:bg-white/45"
          >
            Relationship chart
          </Link>
          <Link
            to={`/projects/${id}/research`}
            className="flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-[13px] text-ink-muted transition-colors hover:bg-white/45"
          >
            Research
          </Link>
        </div>
        <p className="px-5 pb-2 text-[12px] font-medium tracking-[-0.01em] text-paper-muted">
          Chapters
        </p>
        <BinderNav projectId={id} activeChapter={num} />
      </nav>

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto pb-36">
        {!focus && (
        <div className="border-b border-[rgba(74,91,133,0.1)] bg-white/40 px-8 py-5 backdrop-blur-md">
          <div className="mx-auto max-w-[760px]">
            <Breadcrumbs items={[
              { label: "Library", to: "/" },
              { label: id.replace(/-/g, " "), to: `/projects/${id}` },
              { label: `Chapter ${num}` },
            ]} />
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
                  Chapter {num}
                </p>
                <h1 className="font-display text-[24px] font-semibold tracking-tight text-ink-text text-balance">
                  {meta?.title || stages.status}
                </h1>
              </div>
              <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
                <ModeSwitch />
                {meta?.pov && <span>POV {meta.pov}</span>}
                <StatusPill status={stages.status} />
                <Link
                  to={`/projects/${id}/chart`}
                  className="hidden rounded-full border border-[rgba(96,112,153,0.16)] bg-white/55 px-3 py-1 text-[12px] font-medium text-ink-muted transition-colors hover:text-[var(--color-violet)] sm:inline-flex"
                >
                  Chart
                </Link>
                <div className="flex overflow-hidden rounded-full border border-[rgba(96,112,153,0.16)] bg-white/55">
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
                  <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--color-violet)]" />
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
                projectId={id}
                chapterNumber={num}
                hasFinal={stages.final != null}
                canPromote={canPromote}
                promoteFrom={promoteFrom}
                doc={finalDoc}
                wordCount={finalWordCount}
                onChange={(d) => {
                  setFinalDoc(d);
                  setDirty(true);
                }}
                onSave={save}
                onPromote={promote}
                dirty={dirty}
                busy={busy}
                lastSaved={lastSaved}
                focus={focus}
                onToggleFocus={() => setFocus((f) => !f)}
                onCommentSelection={(sel) => {
                  setPendingComment(sel);
                  setShowInspector(true);
                }}
                commentAnchors={commentAnchors}
              />
            ) : (
              <ProvenancePane
                projectId={id}
                chapter={num}
                stage={selected}
                text={stages[selected]}
                provenance={stages.provenance?.[selected]}
                canEditFinal={stages.final != null || stages.draft != null || stages.revised != null}
                onEditManuscript={async () => {
                  const next = await ensureFinal();
                  if (next?.final) selectStage("final");
                }}
                onReviewed={async () => {
                  const next = await api.stages(id, num);
                  setStages(next);
                  if (next.final) {
                    try {
                      const body = await api.getFinalDoc(id, num);
                      setFinalDoc(body.doc as PMDoc);
                      setFinalMarkdown(body.markdown);
                      setFinalWordCount(body.word_count);
                    } catch { /* Final may be empty */ }
                    selectStage("final");
                  }
                }}
              />
            )}
          </div>
        </div>
        </div>

        {!focus && selected === "final" && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-5">
            <div className="w-full max-w-[720px]">
              <ContinueChat
                projectId={id}
                chapter={num}
                disabled={busy != null || isRunning}
                onAccept={async (paragraph) => {
                  const ensured = await ensureFinal();
                  if (!ensured?.final) return;
                  setFinalDoc((prev) => {
                    const content = [...(prev.content || [])];
                    const last = content[content.length - 1];
                    if (
                      last?.type === "paragraph" &&
                      (!last.content || last.content.length === 0)
                    ) {
                      content.pop();
                    }
                    content.push({
                      type: "paragraph",
                      content: [{ type: "text", text: paragraph }],
                    });
                    return { type: "doc", content } as PMDoc;
                  });
                  setDirty(true);
                  selectStage("final");
                }}
              />
            </div>
          </div>
        )}
      </div>

      <QuickCapture
        projectId={id}
        chapterNumber={num}
        onCaptured={() => {
          api.comments(id, num).then(setComments).catch(() => {});
        }}
      />

      <AnimatePresence initial={false}>
        {showInspector && !focus && (
          <motion.aside
            key="inspector-rail"
            initial={{ width: 0, opacity: 0, x: 16 }}
            animate={{ width: 320, opacity: 1, x: 0 }}
            exit={{ width: 0, opacity: 0, x: 16 }}
            transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
            className="shrink-0 self-stretch overflow-hidden"
          >
            <div className="flex h-full min-h-[100%] w-[340px] max-w-[min(340px,100%)] flex-col">
              <Inspector
                id={id}
                num={num}
                currentText={finalMarkdown}
                flush={flush}
                pendingComment={pendingComment}
                onPendingCommentConsumed={() => setPendingComment(null)}
                onClose={() => setShowInspector(false)}
                onCommentsChange={setComments}
                requestedTab={inspectorTab}
                onJumpToComment={(c) => {
                  if (c.from_pos == null || c.to_pos == null) return;
                  selectStage("final");
                  // Selection highlight via decoration is already visible; soft scroll
                  document.querySelector(`[data-comment-id="${c.id}"]`)
                    ?.scrollIntoView({ block: "center", behavior: "smooth" });
                }}
                onRestored={async () => {
                  setDirty(false);
                  await loadFinalDoc();
                  reload();
                }}
              />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
    </Scene>
  );
}

function ProvenancePane({
  projectId, chapter, stage, text, provenance, onReviewed, onEditManuscript, canEditFinal,
}: {
  projectId: string;
  chapter: number;
  stage: StageKey;
  text: string | null;
  provenance?: import("../api/client").StageProvenance;
  onReviewed?: () => void | Promise<void>;
  onEditManuscript?: () => void | Promise<void>;
  canEditFinal?: boolean;
}) {
  const toast = useToast();
  const [diff, setDiff] = useState<import("../api/client").StageDiff | null>(null);
  const [diffBusy, setDiffBusy] = useState(false);
  const [reviewBusy, setReviewBusy] = useState<"accept" | "reject" | null>(null);
  const [editBusy, setEditBusy] = useState(false);

  const prevStage: StageKey | null =
    stage === "draft" ? "outline"
      : stage === "revised" ? "draft"
        : stage === "final" ? "revised"
          : null;

  const canReview = (stage === "draft" || stage === "revised") && text != null;
  const needsReview = canReview && !(provenance?.reviewed_by || "").trim();

  // Drop the previous stage's diff during render, so switching stages never
  // shows one stage's text under another stage's heading.
  const diffKey = text && prevStage ? `${projectId}:${chapter}:${prevStage}>${stage}` : null;
  const [lastDiffKey, setLastDiffKey] = useState(diffKey);
  if (diffKey !== lastDiffKey) {
    setLastDiffKey(diffKey);
    setDiff(null);
    setDiffBusy(diffKey != null);
  }

  useEffect(() => {
    if (!text || !prevStage) return;
    let cancelled = false;
    api.stageDiff(projectId, chapter, prevStage, stage)
      .then((d) => { if (!cancelled) setDiff(d); })
      .catch(() => { if (!cancelled) setDiff(null); })
      .finally(() => { if (!cancelled) setDiffBusy(false); });
    return () => { cancelled = true; };
  }, [projectId, chapter, stage, text, prevStage]);

  async function review(decision: "accept" | "reject") {
    setReviewBusy(decision);
    try {
      const r = await api.reviewStage(projectId, chapter, stage, decision);
      toast(r.message || (decision === "accept" ? "Accepted" : "Rejected"), "success");
      await onReviewed?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setReviewBusy(null);
    }
  }

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
  const agent = provenance?.produced_by_agent || "";
  const model = provenance?.produced_by_model || "";

  return (
    <article className="manuscript-page px-11 py-12">
      <div className="mb-6 space-y-3 text-[12px] font-medium tracking-[-0.01em] text-paper-muted">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-violet)]" />
            Provenance · read-only — edit the Final manuscript
          </div>
          {canEditFinal && (
            <button
              type="button"
              disabled={editBusy}
              onClick={async () => {
                setEditBusy(true);
                try {
                  await onEditManuscript?.();
                } finally {
                  setEditBusy(false);
                }
              }}
              className="rounded-full bg-[var(--color-violet)] px-3.5 py-1.5 text-[12.5px] font-semibold text-white shadow-[0_8px_18px_rgba(104,103,234,0.28)] disabled:opacity-50"
            >
              {editBusy ? "Opening…" : "Edit manuscript"}
            </button>
          )}
        </div>
        {(agent || model || provenance?.reviewed_by) && (
          <p className="pl-3.5 text-[12.5px] text-ink-muted">
            {agent ? `Produced by ${agent}` : "Produced"}
            {model ? ` · ${model}` : ""}
            {provenance?.reviewed_by ? ` · Reviewed by ${provenance.reviewed_by}` : ""}
            {provenance?.word_count ? ` · ${provenance.word_count} words` : ""}
          </p>
        )}
      </div>

      {canReview && (
        <div className={`mb-8 rounded-2xl border px-4 py-3 ${
          needsReview
            ? "border-[rgba(104,103,234,0.28)] bg-[rgba(104,103,234,0.06)]"
            : "border-[rgba(74,91,133,0.12)] bg-white/55"
        }`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[12px] font-semibold text-ink-text">
                {needsReview ? "Needs review" : "Reviewed"}
              </p>
              <p className="mt-0.5 text-[12.5px] text-ink-muted">
                {needsReview
                  ? "Accept to promote into Final. Reject keeps this stage as provenance only."
                  : `Accepted${provenance?.reviewed_at ? ` · ${provenance.reviewed_at}` : ""}`}
              </p>
            </div>
            {needsReview && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={reviewBusy != null}
                  onClick={() => review("reject")}
                  className="rounded-full border border-[rgba(96,112,153,0.2)] bg-white/70 px-3.5 py-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:text-ink-text disabled:opacity-50"
                >
                  {reviewBusy === "reject" ? "Rejecting…" : "Reject"}
                </button>
                <button
                  type="button"
                  disabled={reviewBusy != null}
                  onClick={() => review("accept")}
                  className="rounded-full bg-[var(--color-violet)] px-3.5 py-1.5 text-[12.5px] font-semibold text-white shadow-[0_8px_18px_rgba(104,103,234,0.28)] transition-opacity disabled:opacity-50"
                >
                  {reviewBusy === "accept" ? "Accepting…" : "Accept"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {prevStage && (
        <div className="mb-8 rounded-2xl border border-[rgba(74,91,133,0.12)] bg-white/55 px-4 py-3">
          <p className="text-[12px] font-semibold text-ink-text">
            What changed vs {cap(prevStage)}
          </p>
          {diffBusy && <p className="mt-1 text-[12.5px] text-ink-muted">Comparing…</p>}
          {diff && !diffBusy && (
            <>
              <p className="mt-1 text-[12.5px] text-ink-muted">{diff.summary}</p>
              {(diff.added_lines.length > 0 || diff.removed_lines.length > 0) && (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {diff.added_lines.length > 0 && (
                    <div>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[#2f8a57]">Added</p>
                      <ul className="max-h-40 space-y-1 overflow-y-auto text-[12px] leading-relaxed text-ink-text">
                        {diff.added_lines.slice(0, 8).map((ln, i) => (
                          <li key={i} className="rounded-lg bg-[#e9f7ef]/70 px-2 py-1">{ln}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {diff.removed_lines.length > 0 && (
                    <div>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[#c85177]">Removed</p>
                      <ul className="max-h-40 space-y-1 overflow-y-auto text-[12px] leading-relaxed text-ink-text">
                        {diff.removed_lines.slice(0, 8).map((ln, i) => (
                          <li key={i} className="rounded-lg bg-[#ffeaf1]/70 px-2 py-1">{ln}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className={outline ? "prose-outline" : "prose-manuscript"}>
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
    </article>
  );
}

function Empty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="manuscript-page px-11 py-14 text-center">
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
      className="btn-secondary disabled:opacity-40"
    >
      {running ? "Running…" : label}
    </button>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
