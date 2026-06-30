import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  api,
  type ChapterDetail,
  type ChapterStages,
  type ChapterSummary,
  type RegeneratePreview,
} from "../api/client";
import StatusPill from "../components/StatusPill";
import PipelineFlow, { type StageKey } from "../components/PipelineFlow";
import FinalEditor from "../components/FinalEditor";
import MarkdownEditor from "../components/MarkdownEditor";
import Inspector from "../components/Inspector";
import Breadcrumbs from "../components/Breadcrumbs";
import DeleteButton from "../components/DeleteButton";
import { RenumberChapterModal } from "../components/CodexEditors";
import { useToast } from "../components/Toaster";
import { useConfirm } from "../components/Confirm";
import { useRunPhase } from "../hooks/useRunPhase";
import { useBackgroundJob, type BackgroundJobKind } from "../hooks/useBackgroundJob";
import EditorSaveBar, { formatSavedAt } from "../components/EditorSaveBar";
import PanelToggle from "../components/PanelToggle";
import { ChapterPipelineDot } from "../components/ChapterPipelineStatus";
import PendingAiStar from "../components/PendingAiStar";
import ResumeWorkflowDot from "../components/ResumeWorkflowDot";
import { pipelineStepFromSummary } from "../lib/chapterPipeline";
import { useLayoutPrefs } from "../context/LayoutPrefs";
import { useWorkflowMarkers } from "../hooks/useWorkflowMarkers";
import {
  setChapterPreviewPending,
  hasChapterPreviewPending,
} from "../lib/chapterPreviewPending";
import {
  recordChapterFunction,
  recordChapterVisit,
  CHAPTER_FUNCTION_LABELS,
  type ChapterFunction,
} from "../lib/chapterWorkflow";

const STAGE_KEYS: StageKey[] = ["outline", "draft", "revised", "final"];

type MineKind = "plots" | "characters" | "bible";

const MINE_JOB_KIND: Record<MineKind, BackgroundJobKind> = {
  plots: "mine-plots",
  characters: "mine-characters",
  bible: "mine-bible",
};

const MINE_LABELS: Record<MineKind, string> = {
  plots: "Plots & subplots",
  characters: "Characters",
  bible: "Story bible",
};

const EXPAND_MARKER_RE = /\[\[(?:expand|ai)\s*:/gi;

function countExpandMarkers(text: string): number {
  return (text.match(EXPAND_MARKER_RE) || []).length;
}

function firstPresent(s: ChapterStages): StageKey {
  if (s.final != null) return "final";
  if (s.revised != null) return "revised";
  if (s.draft != null) return "draft";
  return "outline";
}

function regenerateSource(stages: ChapterStages, selected: StageKey): string {
  if (selected === "draft" && stages.draft) return "draft";
  if (selected === "revised" && stages.revised) return "revised";
  if (selected === "final" && stages.final) return "final";
  if (stages.draft) return "draft";
  if (stages.final) return "final";
  if (stages.revised) return "revised";
  return "draft";
}

function hasRegenerateSource(stages: ChapterStages): boolean {
  return !!(stages.draft || stages.revised || stages.final);
}

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const num = Number(n);
  const toast = useToast();
  const confirm = useConfirm();
  const [searchParams, setSearchParams] = useSearchParams();

  const [meta, setMeta] = useState<ChapterDetail | null>(null);
  const [stages, setStages] = useState<ChapterStages | null>(null);
  const [siblings, setSiblings] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [finalText, setFinalText] = useState("");
  const [draftText, setDraftText] = useState("");
  const [revisedText, setRevisedText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [draftDirty, setDraftDirty] = useState(false);
  const [revisedDirty, setRevisedDirty] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const [expandPreview, setExpandPreview] = useState<RegeneratePreview | null>(null);
  const [expandPreviewText, setExpandPreviewText] = useState("");
  const [regeneratePreview, setRegeneratePreview] = useState<RegeneratePreview | null>(null);
  const [previewText, setPreviewText] = useState("");
  const [regenInstructions, setRegenInstructions] = useState("");
  const [applyNotesToOutline, setApplyNotesToOutline] = useState(false);
  const [outlineGenerating, setOutlineGenerating] = useState(false);
  const [outlinePreview, setOutlinePreview] = useState<RegeneratePreview | null>(null);
  const [outlinePreviewText, setOutlinePreviewText] = useState("");
  const [outlineInstructions, setOutlineInstructions] = useState("");
  const [busy, setBusy] = useState<null | "saving" | "promoting" | "reopening">(null);
  const [focus, setFocus] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [draftLastSaved, setDraftLastSaved] = useState<string | null>(null);
  const [revisedLastSaved, setRevisedLastSaved] = useState<string | null>(null);
  const [showBinder, setShowBinder] = useState(true);
  const [showInspector, setShowInspector] = useState(true);
  const [renumberOpen, setRenumberOpen] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [titleSaving, setTitleSaving] = useState(false);
  const navigate = useNavigate();
  const { showLibrary, toggleLibrary } = useLayoutPrefs();
  const { lastAccessedChapter, lastFunction: lastFn } = useWorkflowMarkers(id, num);
  const hasPreviewPending =
    Boolean(regeneratePreview || outlinePreview || expandPreview)
    || hasChapterPreviewPending(id, num);

  // refs so the unmount/unload/autosave handlers see the latest values
  const dirtyRef = useRef(false);
  const draftDirtyRef = useRef(false);
  const revisedDirtyRef = useRef(false);
  const titleFocused = useRef(false);
  const textRef = useRef("");
  const draftTextRef = useRef("");
  const revisedTextRef = useRef("");
  const busyRef = useRef<typeof busy>(null);
  const phaseAfterDone = useRef<StageKey | null>(null);
  const pendingOutlineAfterReviseRef = useRef(false);
  const startGenerateOutlineRef = useRef<(mode?: "text" | "notes") => Promise<void>>(async () => {});
  const saveDraftRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  const saveRevisedRef = useRef<(opts?: { silent?: boolean }) => Promise<void>>(async () => {});
  dirtyRef.current = dirty;
  draftDirtyRef.current = draftDirty;
  revisedDirtyRef.current = revisedDirty;
  textRef.current = finalText;
  draftTextRef.current = draftText;
  revisedTextRef.current = revisedText;
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

  function combinedOutlineInstructions(): string {
    const outline = outlineInstructions.trim();
    const revision = regenInstructions.trim();
    if (applyNotesToOutline && revision) {
      if (outline) {
        return `${outline}\n\n## Revision notes\n${revision}`;
      }
      return revision;
    }
    return outline;
  }

  const hasOutlineNotes = Boolean(combinedOutlineInstructions().trim());

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
        if (!draftDirtyRef.current) {
          setDraftText(s.draft ?? "");
        }
        if (!revisedDirtyRef.current) {
          setRevisedText(s.revised ?? "");
        }
      })
      .catch((e) => setError(String(e)));
    api.getRegeneratePreview(id, num).then((p) => {
      setRegeneratePreview(p);
      if (p) setPreviewText(p.text);
      else setPreviewText("");
    }).catch(() => {
      setRegeneratePreview(null);
      setPreviewText("");
    });
    api.getOutlinePreview(id, num).then((p) => {
      setOutlinePreview(p);
      if (p) setOutlinePreviewText(p.text);
      else setOutlinePreviewText("");
    }).catch(() => {
      setOutlinePreview(null);
      setOutlinePreviewText("");
    });
    api.getExpandPreview(id, num).then((p) => {
      setExpandPreview(p);
      if (p) setExpandPreviewText(p.text);
      else setExpandPreviewText("");
    }).catch(() => {
      setExpandPreview(null);
      setExpandPreviewText("");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, num]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    recordChapterVisit(id, num);
  }, [id, num]);

  useEffect(() => {
    const pending = Boolean(regeneratePreview || outlinePreview || expandPreview);
    setChapterPreviewPending(id, num, pending);
  }, [id, num, regeneratePreview, outlinePreview, expandPreview]);

  useEffect(() => {
    if (!titleFocused.current) {
      setTitleDraft(meta?.title ?? "");
    }
  }, [meta?.title, num]);

  async function saveChapterTitle() {
    const trimmed = titleDraft.trim();
    if (trimmed === (meta?.title ?? "").trim()) return;
    setTitleSaving(true);
    try {
      const updated = await api.updateChapter(id, num, { title: trimmed });
      setMeta((m) => (m ? { ...m, title: updated.title } : m));
      setSiblings((list) =>
        list.map((c) => (c.number === num ? { ...c, title: updated.title } : c)),
      );
      setTitleDraft(updated.title);
      toast(trimmed ? "Chapter title saved" : "Chapter title cleared", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      setTitleDraft(meta?.title ?? "");
    } finally {
      setTitleSaving(false);
    }
  }

  const handlePhaseDone = useCallback(() => {
    reload();
    if (phaseAfterDone.current) {
      selectStage(phaseAfterDone.current);
      phaseAfterDone.current = null;
    }
    if (pendingOutlineAfterReviseRef.current) {
      pendingOutlineAfterReviseRef.current = false;
      void startGenerateOutlineRef.current("notes");
    }
  }, [reload]);

  const { run, runningStage, isRunning } = useRunPhase(id, handlePhaseDone);
  const { watchBackgroundJob, isProjectJobRunning } = useBackgroundJob();
  const chapterScope = String(num);

  function isMining(kind: MineKind) {
    return isProjectJobRunning(MINE_JOB_KIND[kind], id, chapterScope);
  }

  function runChapter(fn: ChapterFunction, phase: string, params: Record<string, unknown> = {}) {
    recordChapterFunction(id, num, fn);
    void run(phase, params);
  }

  function runRevise() {
    void (async () => {
      recordChapterFunction(id, num, "edit");
      if (revisedDirtyRef.current) await saveRevised();
      else if (draftDirtyRef.current) await saveDraft();
      pendingOutlineAfterReviseRef.current =
        applyNotesToOutline && Boolean(regenInstructions.trim());
      phaseAfterDone.current = "revised";
      void run("edit", {
        number: num,
        instructions: regenInstructions.trim(),
      });
    })();
  }

  async function copyRevisedToDraft() {
    if (!stages?.revised && !revisedText.trim()) {
      toast("No revised text to copy", "error");
      return;
    }
    if (revisedDirtyRef.current) await saveRevised();
    setBusy("saving");
    try {
      const text = revisedTextRef.current;
      const r = await api.saveDraft(id, num, text);
      setDraftText(r.draft);
      setDraftDirty(false);
      setDraftLastSaved(formatSavedAt());
      setStages((s) => (s ? { ...s, draft: r.draft } : s));
      toast("Copied Revised → Draft (optional — Revise already uses Revised)", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  // Warn on tab close / refresh with unsaved edits
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current || draftDirtyRef.current || revisedDirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      if (dirtyRef.current) api.saveFinal(id, num, textRef.current).catch(() => {});
      if (draftDirtyRef.current) api.saveDraft(id, num, draftTextRef.current).catch(() => {});
      if (revisedDirtyRef.current) api.saveRevised(id, num, revisedTextRef.current).catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, num]);

  // Debounced autosave — final, draft, and revised
  const saveRef = useRef<() => void>(() => {});
  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      if (dirtyRef.current && busyRef.current == null) saveRef.current();
    }, 1500);
    return () => clearTimeout(t);
  }, [finalText, dirty]);

  useEffect(() => {
    if (!draftDirty) return;
    const t = setTimeout(() => {
      if (draftDirtyRef.current && busyRef.current == null) {
        void saveDraftRef.current({ silent: true });
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [draftText, draftDirty]);

  useEffect(() => {
    if (!revisedDirty) return;
    const t = setTimeout(() => {
      if (revisedDirtyRef.current && busyRef.current == null) {
        void saveRevisedRef.current({ silent: true });
      }
    }, 1500);
    return () => clearTimeout(t);
  }, [revisedText, revisedDirty]);

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

  async function saveDraft(opts?: { silent?: boolean }) {
    setBusy("saving");
    try {
      const r = await api.saveDraft(id, num, draftTextRef.current);
      setStages((s) => (s ? { ...s, draft: r.draft, status: "drafted" } : s));
      setDraftDirty(false);
      setDraftLastSaved(formatSavedAt());
      if (!opts?.silent) {
        toast("Draft saved", "success");
        reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveDraftRef.current = saveDraft;

  async function saveRevised(opts?: { silent?: boolean }) {
    setBusy("saving");
    try {
      const r = await api.saveRevised(id, num, revisedTextRef.current);
      setStages((s) => (s ? { ...s, revised: r.revised, status: "edited" } : s));
      setRevisedDirty(false);
      setRevisedLastSaved(formatSavedAt());
      if (!opts?.silent) {
        toast("Revision saved", "success");
        reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }
  saveRevisedRef.current = saveRevised;

  async function pollJob(jobId: string): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setInterval(async () => {
        try {
          const s = await api.getJob(jobId);
          if (s.status === "running") return;
          window.clearInterval(timer);
          if (s.status === "done") resolve();
          else reject(new Error(s.error ?? "Job failed"));
        } catch (e) {
          window.clearInterval(timer);
          reject(e);
        }
      }, 1500);
    });
  }

  async function startRegenerate() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to regenerate from", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setRegenerating(true);
    recordChapterFunction(id, num, "regenerate");
    try {
      const job = await api.regenerateChapter(id, num, {
        source,
        instructions: regenInstructions.trim(),
      });
      toast("Regenerating chapter…", "success");
      await pollJob(job.job_id);
      const preview = await api.getRegeneratePreview(id, num);
      if (!preview) throw new Error("Regeneration finished but no preview was saved");
      setRegeneratePreview(preview);
      setPreviewText(preview.text);
      toast("Regeneration ready — review and keep or discard", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setRegenerating(false);
    }
  }

  async function startExpandPlaceholders() {
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to expand in", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    setExpanding(true);
    recordChapterFunction(id, num, "expand");
    try {
      const job = await api.expandPlaceholders(id, num, {
        source,
        instructions: regenInstructions.trim(),
      });
      toast("Expanding placeholders…", "success");
      await pollJob(job.job_id);
      const preview = await api.getExpandPreview(id, num);
      if (!preview) throw new Error("Expansion finished but no preview was saved");
      setExpandPreview(preview);
      setExpandPreviewText(preview.text);
      toast("Expansion ready — review and keep or discard", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setExpanding(false);
    }
  }

  async function applyExpandPreview() {
    if (!expandPreview) return;
    try {
      const r = await api.applyExpandPreview(id, num, {
        text: expandPreviewText,
        target: expandPreview.source,
      });
      setExpandPreview(null);
      setExpandPreviewText("");
      toast(`Kept expansion → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      if (r.target === "draft") selectStage("draft");
      else if (r.target === "final") selectStage("final");
      else selectStage("revised");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardExpandPreview() {
    const ok = await confirm({
      title: "Discard expansion",
      message: "Discard this expanded preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardExpandPreview(id, num);
      setExpandPreview(null);
      setExpandPreviewText("");
      toast("Discarded expansion", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function applyRegenerate() {
    if (!regeneratePreview) return;
    try {
      const r = await api.applyRegenerate(id, num, {
        text: previewText,
        target: regeneratePreview.source,
      });
      setRegeneratePreview(null);
      setPreviewText("");
      toast(`Kept regeneration → ${r.target} (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      if (r.target === "draft") selectStage("draft");
      else if (r.target === "final") selectStage("final");
      else selectStage("revised");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardRegenerate() {
    const ok = await confirm({
      title: "Discard regeneration",
      message: "Discard this regenerated draft? The preview will be deleted.",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardRegenerate(id, num);
      setRegeneratePreview(null);
      setPreviewText("");
      toast("Discarded regeneration", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function startGenerateOutline(mode: "text" | "notes" = "text") {
    if (mode === "text" && (!stages || !hasRegenerateSource(stages))) {
      toast("No chapter text to outline — add draft or final prose first", "error");
      return;
    }
    if (mode === "notes" && !combinedOutlineInstructions()) {
      toast("Enter outline notes or revision notes (with “apply to outline” checked)", "error");
      return;
    }
    if (mode === "text") {
      if (selected === "draft" && draftDirty) await saveDraft();
      if (selected === "revised" && revisedDirty) await saveRevised();
      if (selected === "final" && dirty) await save();
    }
    const source = mode === "notes" ? "notes" : regenerateSource(stages!, selected);
    setOutlineGenerating(true);
    recordChapterFunction(id, num, mode === "notes" ? "outline-notes" : "outline-text");
    try {
      const job = await api.generateOutline(id, num, {
        source,
        instructions: combinedOutlineInstructions(),
      });
      toast(
        mode === "notes"
          ? "Generating outline from your notes…"
          : "Generating outline from chapter text…",
        "success",
      );
      await pollJob(job.job_id);
      const preview = await api.getOutlinePreview(id, num);
      if (!preview) throw new Error("Outline generation finished but no preview was saved");
      setOutlinePreview(preview);
      setOutlinePreviewText(preview.text);
      toast("Outline ready — review and keep or discard", "success");
      selectStage("outline");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setOutlineGenerating(false);
    }
  }
  startGenerateOutlineRef.current = startGenerateOutline;

  async function applyOutlinePreview() {
    if (!outlinePreview) return;
    try {
      const r = await api.applyOutlinePreview(id, num, { text: outlinePreviewText });
      setOutlinePreview(null);
      setOutlinePreviewText("");
      toast(`Outline saved (${r.word_count.toLocaleString()} words)`, "success");
      reload();
      selectStage("outline");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function discardOutlinePreview() {
    const ok = await confirm({
      title: "Discard outline",
      message: "Discard this generated outline preview?",
      confirmLabel: "Discard",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.discardOutlinePreview(id, num);
      setOutlinePreview(null);
      setOutlinePreviewText("");
      toast("Discarded outline preview", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function extractMetadata() {
    if (draftDirty) await saveDraft();
    setExtracting(true);
    recordChapterFunction(id, num, "extract");
    try {
      const job = await api.extractChapter(id, num);
      await pollJob(job.job_id);
      toast("Extracted characters, plot & world facts", "success");
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setExtracting(false);
    }
  }

  async function mineFromChapter(kind: MineKind) {
    if (isMining(kind)) return;
    if (!stages || !hasRegenerateSource(stages)) {
      toast("No chapter text to mine — add draft, revised, or final prose first", "error");
      return;
    }
    if (selected === "draft" && draftDirty) await saveDraft();
    if (selected === "revised" && revisedDirty) await saveRevised();
    if (selected === "final" && dirty) await save();
    const source = regenerateSource(stages, selected);
    const mineFn: ChapterFunction =
      kind === "plots" ? "mine-plots" : kind === "characters" ? "mine-characters" : "mine-bible";
    recordChapterFunction(id, num, mineFn);
    try {
      const job = await api.mineChapter(id, num, kind, source);
      toast(`Mining ${MINE_LABELS[kind].toLowerCase()} from chapter text…`, "success");
      watchBackgroundJob(job.job_id, {
        label: MINE_LABELS[kind],
        kind: MINE_JOB_KIND[kind],
        projectId: id,
        scope: chapterScope,
        successMessage: `Updated ${MINE_LABELS[kind].toLowerCase()} from chapter ${num}`,
        onSuccess: () => reload(),
      });
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function deleteThisChapter() {
    try {
      await api.deleteChapter(id, num);
      toast(`Deleted chapter ${num}`, "success");
      navigate(`/projects/${id}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function promote() {
    setBusy("promoting");
    try {
      const r = await api.promoteFinal(id, num);
      setFinalText(r.final);
      setDirty(false);
      setStages((s) => (s ? { ...s, final: r.final } : s));
      selectStage("final");
      api.chapters(id).then(setSiblings).catch(() => {});
      toast("Promoted to Final", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  async function reopenForRevision() {
    const ok = await confirm({
      title: "Reopen for revision?",
      message:
        "This removes Final, clears validation and approval, and copies Final text into Draft "
        + "and Revised (when a Final exists) so you can run Revise again.",
      confirmLabel: "Reopen",
      danger: true,
    });
    if (!ok) return;
    setBusy("reopening");
    try {
      const r = await api.unfinalizeChapter(id, num);
      setStages({
        number: r.number,
        status: r.status,
        outline: r.outline,
        draft: r.draft,
        revised: r.revised,
        final: r.final,
        continuity: null,
      });
      setMeta((m) => (m ? { ...m, status: r.status, word_count: r.word_count } : m));
      setFinalText("");
      setDraftText(r.draft ?? "");
      setRevisedText(r.revised ?? "");
      setDirty(false);
      setDraftDirty(false);
      setRevisedDirty(false);
      selectStage("revised");
      api.chapters(id).then(setSiblings).catch(() => {});
      toast("Chapter reopened for revision", "success");
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
      setLastSaved(formatSavedAt());
      api.chapters(id).then(setSiblings).catch(() => {});
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
  const canReopen =
    stages.final != null
    || stages.status === "complete"
    || stages.status === "validated"
    || stages.continuity != null;
  const reviseUses = stages.revised != null ? "Revised" : stages.draft != null ? "Draft" : null;
  const inRevisionLoop = stages.draft != null || stages.revised != null;
  const stageEditorText =
    selected === "draft" ? draftText
      : selected === "revised" ? revisedText
        : selected === "final" ? finalText
          : "";
  const expandMarkerCount = countExpandMarkers(stageEditorText);

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
          {siblings.map((c) => {
            const isLastAccessed = lastAccessedChapter === c.number;
            const cPreview = hasChapterPreviewPending(id, c.number);
            return (
            <Link
              key={c.number}
              to={`/projects/${id}/chapters/${c.number}`}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                c.number === num
                  ? "bg-amber/15 font-medium text-ink-text"
                  : "text-ink-muted hover:bg-ink/5"
              }`}
            >
              {isLastAccessed && (
                <ResumeWorkflowDot title="Last chapter you worked in" />
              )}
              <ChapterPipelineDot step={pipelineStepFromSummary(c)} size="sm" />
              <span className="nums shrink-0 font-mono text-[11px] text-paper-muted">{c.number}</span>
              <span className="min-w-0 truncate">{c.title || "Untitled"}</span>
              {cPreview && <PendingAiStar title="AI preview ready to review" />}
            </Link>
          );})}
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
              { label: meta?.title?.trim() ? meta.title : `Chapter ${num}` },
            ]} />
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-[11.5px] font-semibold uppercase tracking-[0.16em] text-amber-deep">
                  Chapter {num}
                  {hasPreviewPending && <PendingAiStar title="AI preview ready to review" />}
                </p>
                <input
                  type="text"
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  onFocus={() => { titleFocused.current = true; }}
                  onBlur={() => {
                    titleFocused.current = false;
                    void saveChapterTitle();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      (e.target as HTMLInputElement).blur();
                    }
                  }}
                  placeholder="Untitled chapter"
                  disabled={titleSaving}
                  aria-label="Chapter title"
                  className="mt-0.5 w-full max-w-xl border-b border-transparent bg-transparent font-display text-[24px] font-semibold tracking-tight text-ink-text outline-none transition-colors placeholder:text-ink-muted/60 hover:border-paper-line focus:border-amber-deep disabled:opacity-60"
                />
              </div>
              <div className="flex items-center gap-3 text-[12.5px] text-ink-muted">
                {meta?.pov && <span>POV {meta.pov}</span>}
                <StatusPill status={stages.status} />
                <button type="button" onClick={() => setRenumberOpen(true)}
                        className="rounded-md px-2 py-1 text-[12px] font-semibold text-ink-muted hover:bg-ink/5 hover:text-ink-text"
                        title="Renumber chapter">
                  # Renumber
                </button>
                <DeleteButton
                  label={`Delete chapter ${num}`}
                  title="Delete chapter"
                  message={`Delete chapter ${num}${meta?.title ? `: "${meta.title}"` : ""}? All files and notes for this chapter will be removed.`}
                  confirmLabel="Delete chapter"
                  onConfirm={deleteThisChapter}
                />
                <div className="flex overflow-hidden rounded-lg border border-paper-line">
                  <PanelToggle on={showLibrary} onClick={toggleLibrary} label="Library" />
                  <PanelToggle on={showBinder} onClick={() => setShowBinder((b) => !b)} label="Binder" border />
                  <PanelToggle on={showInspector} onClick={() => setShowInspector((s) => !s)} label="Notes" border />
                </div>
              </div>
            </div>
            <PipelineFlow stages={stages} selected={selected} onSelect={selectStage} />

            {inRevisionLoop && !stages.final && (
              <div className="mt-3 rounded-lg border border-amber/30 bg-amber/5 px-4 py-3 text-[13px] leading-relaxed text-ink-text">
                <p className="font-semibold text-ink-text">Your revision loop</p>
                <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-ink-muted">
                  <li><strong className="text-ink-text">Draft</strong> — first prose (Generate Draft or paste)</li>
                  <li><strong className="text-ink-text">Revise</strong> — Editor pass → opens <strong className="text-ink-text">Revised</strong></li>
                  <li><strong className="text-ink-text">You edit Revised</strong> — change text directly; it autosaves</li>
                  <li><strong className="text-ink-text">Revise again</strong> — uses your saved Revised{reviseUses ? ` (next pass: ${reviseUses})` : ""}, not Draft</li>
                  <li>When happy: Validate → Approve → Promote to <strong className="text-ink-text">Final</strong></li>
                </ol>
                <p className="mt-2 text-[12px] text-ink-muted">
                  Draft is kept as the original snapshot. You do <em>not</em> need to copy back to Draft to re-revise.
                </p>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <RunButton label="Generate Draft" running={runningStage === "write"}
                         disabled={isRunning} resume={lastFn === "write"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS.write}
                         onClick={() => runChapter("write", "write", { number: num })} />
              <RunButton label="Revise" running={runningStage === "edit"}
                         disabled={isRunning || (stages.draft == null && stages.revised == null)}
                         resume={lastFn === "edit"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS.edit}
                         onClick={runRevise} />
              {reviseUses && (
                <span className="text-[12px] text-ink-muted">
                  Revise reads <strong className="font-medium text-ink-text">{reviseUses}</strong>
                </span>
              )}
              <RunButton label="Validate" running={runningStage === "validate"}
                         disabled={isRunning || (stages.draft == null && stages.revised == null)}
                         resume={lastFn === "validate"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS.validate}
                         onClick={() => runChapter("validate", "validate", { number: num })} />
              <RunButton label="Approve" running={runningStage === "approve"}
                         disabled={isRunning} resume={lastFn === "approve"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS.approve}
                         onClick={() => runChapter("approve", "approve", { number: num })} />
              {canReopen && (
                <button
                  type="button"
                  onClick={reopenForRevision}
                  disabled={isRunning || busy != null}
                  className="rounded-lg border border-paper-line px-3 py-1.5 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
                >
                  {busy === "reopening" ? "Reopening…" : "Reopen for revision"}
                </button>
              )}
              <RunButton label={regenerating ? "Regenerating…" : "Regenerate"}
                         running={regenerating}
                         disabled={isRunning || regenerating || expanding || !hasRegenerateSource(stages)}
                         resume={lastFn === "regenerate"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS.regenerate}
                         onClick={() => startRegenerate()} />
              <RunButton
                label={expanding ? "Expanding…" : expandMarkerCount > 0 ? `Expand placeholders (${expandMarkerCount})` : "Expand placeholders"}
                running={expanding}
                disabled={isRunning || expanding || regenerating || expandMarkerCount === 0}
                resume={lastFn === "expand"}
                resumeLabel={CHAPTER_FUNCTION_LABELS.expand}
                onClick={() => startExpandPlaceholders()}
              />
              <RunButton label={outlineGenerating ? "Outlining…" : "Outline from notes"}
                         running={outlineGenerating}
                         disabled={isRunning || outlineGenerating || !hasOutlineNotes}
                         resume={lastFn === "outline-notes"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS["outline-notes"]}
                         onClick={() => startGenerateOutline("notes")} />
              <RunButton label={outlineGenerating ? "Outlining…" : "Outline from text"}
                         running={outlineGenerating}
                         disabled={isRunning || outlineGenerating || !hasRegenerateSource(stages)}
                         resume={lastFn === "outline-text"}
                         resumeLabel={CHAPTER_FUNCTION_LABELS["outline-text"]}
                         onClick={() => startGenerateOutline("text")} />
              {isRunning && (
                <span className="ml-1 inline-flex items-center gap-2 text-[12px] text-ink-muted" aria-live="polite">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-amber-deep" />
                  Agent working…
                </span>
              )}
            </div>
            {stages && hasRegenerateSource(stages) && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-paper-line/60 pt-3">
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                  Mine chapter text
                </span>
                <MineButton label="Plots & subplots" running={isMining("plots")} disabled={isRunning || isMining("plots")}
                            resume={lastFn === "mine-plots"}
                            resumeLabel={CHAPTER_FUNCTION_LABELS["mine-plots"]}
                            onClick={() => mineFromChapter("plots")} />
                <MineButton label="Characters" running={isMining("characters")} disabled={isRunning || isMining("characters")}
                            resume={lastFn === "mine-characters"}
                            resumeLabel={CHAPTER_FUNCTION_LABELS["mine-characters"]}
                            onClick={() => mineFromChapter("characters")} />
                <MineButton label="Story bible" running={isMining("bible")} disabled={isRunning || isMining("bible")}
                            resume={lastFn === "mine-bible"}
                            resumeLabel={CHAPTER_FUNCTION_LABELS["mine-bible"]}
                            onClick={() => mineFromChapter("bible")} />
                <span className="text-[12px] text-ink-muted">
                  Uses {regenerateSource(stages, selected)} stage · LM Studio · run any or all in parallel
                </span>
              </div>
            )}
            {!regeneratePreview && !outlinePreview && !expandPreview && (
              <div className="mt-3 flex flex-col gap-2">
                <p className="text-[12px] text-ink-muted">
                  Insert AI sections in Draft or Revised with{" "}
                  <code className="rounded bg-ink/5 px-1 py-0.5 text-[11px]">[[expand: your instruction]]</code>
                  {" "}then click <strong>Expand placeholders</strong>.
                </p>
                <input
                  className="w-full max-w-xl rounded-lg border border-paper-line bg-paper-card px-3 py-2 text-[13px] text-ink-text placeholder:text-ink-muted"
                  value={regenInstructions}
                  onChange={(e) => setRegenInstructions(e.target.value)}
                  placeholder="Revision notes for Revise & Regenerate (e.g. cut exposition, fix the ending…)"
                  disabled={regenerating || isRunning}
                />
                <label className="flex max-w-xl cursor-pointer items-center gap-2 text-[12px] text-ink-muted">
                  <input
                    type="checkbox"
                    checked={applyNotesToOutline}
                    onChange={(e) => setApplyNotesToOutline(e.target.checked)}
                    disabled={regenerating || isRunning || outlineGenerating}
                    className="rounded border-paper-line"
                  />
                  Also apply revision notes to outline (Revise, Outline from notes/text)
                </label>
                <textarea
                  className="w-full max-w-xl rounded-lg border border-paper-line bg-paper-card px-3 py-2 text-[13px] leading-relaxed text-ink-text placeholder:text-ink-muted"
                  rows={4}
                  value={outlineInstructions}
                  onChange={(e) => setOutlineInstructions(e.target.value)}
                  placeholder="Outline notes & direction — POV, beats, what must happen, tone, ending hook. Merged with revision notes when the checkbox above is on."
                  disabled={outlineGenerating || isRunning}
                />
              </div>
            )}
          </div>
        </div>
        )}

        <div className={focus ? "px-6 py-8" : "px-8 py-10"}>
          <div className={`mx-auto ${selected === "final" ? "max-w-[960px]" : "max-w-[760px]"}`}>
            {outlinePreview && (
              <RegeneratePreviewPanel
                preview={outlinePreview}
                text={outlinePreviewText}
                onChange={setOutlinePreviewText}
                onKeep={applyOutlinePreview}
                onDiscard={discardOutlinePreview}
                title="Generated outline"
                keepLabel="Keep outline"
                description={
                  outlinePreview.source === "notes"
                    ? "Generated from your outline notes. Edit beats if needed, then keep to save as the chapter outline."
                    : `Reverse-engineered from ${outlinePreview.source} prose (${outlinePreview.original_word_count.toLocaleString()} words). Edit beats if needed, then keep to save as the chapter outline.`
                }
              />
            )}
            {expandPreview && (
              <RegeneratePreviewPanel
                preview={expandPreview}
                text={expandPreviewText}
                onChange={setExpandPreviewText}
                onKeep={applyExpandPreview}
                onDiscard={discardExpandPreview}
                title="Expanded placeholders"
                keepLabel={`Keep → ${expandPreview.source}`}
                description={`Filled ${expandPreview.placeholder_count ?? "?"} placeholder(s) in ${expandPreview.source} prose (${expandPreview.original_word_count.toLocaleString()} → ${expandPreview.preview_word_count.toLocaleString()} words). Edit if needed, then keep.`}
              />
            )}
            {regeneratePreview && (
              <RegeneratePreviewPanel
                preview={regeneratePreview}
                text={previewText}
                onChange={setPreviewText}
                onKeep={applyRegenerate}
                onDiscard={discardRegenerate}
              />
            )}
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
                onPromote={promote}
                onReopen={reopenForRevision}
                canReopen={canReopen}
                dirty={dirty}
                busy={busy}
                lastSaved={lastSaved}
                focus={focus}
                onToggleFocus={() => setFocus((f) => !f)}
              />
            ) : selected === "revised" ? (
              stages.revised == null ? (
                <ProvenancePane
                  stage="revised"
                  text={null}
                  canGenerateOutline={hasRegenerateSource(stages)}
                  onGenerateOutline={() => startGenerateOutline("text")}
                  onGenerateOutlineFromNotes={() => startGenerateOutline("notes")}
                  outlineNotes={combinedOutlineInstructions()}
                  outlineGenerating={outlineGenerating}
                />
              ) : (
                <div>
                  <EditorSaveBar
                    dirty={revisedDirty}
                    saving={busy === "saving"}
                    lastSaved={revisedLastSaved}
                    autosaveOnly
                    hint={<>Edit this text, then click <strong>Revise</strong> again (or add notes above). Draft is unchanged.</>}
                  />
                  <div className="mb-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void copyRevisedToDraft()}
                      disabled={busy != null || !revisedText.trim()}
                      className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-medium text-ink-muted hover:bg-ink/5 disabled:opacity-40"
                      title="Optional — only if you want Draft to match Revised. Revise already uses Revised."
                    >
                      Copy Revised → Draft
                    </button>
                  </div>
                  <article className="rounded-md bg-paper-card px-8 py-10 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[50vh]">
                    <MarkdownEditor value={revisedText}
                                    onChange={(v) => { setRevisedText(v); setRevisedDirty(true); }}
                                    placeholder="Revised chapter prose…" />
                  </article>
                </div>
              )
            ) : selected === "draft" ? (
              <div>
                <EditorSaveBar
                  dirty={draftDirty}
                  saving={busy === "saving"}
                  lastSaved={draftLastSaved}
                  autosaveOnly
                  hint="Paste or edit prose, then extract metadata to update cast and plot threads."
                />
                <div className="mb-3">
                  <button type="button" onClick={extractMetadata} disabled={extracting || isRunning}
                          className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
                    {extracting ? "Extracting…" : "Extract metadata (LM Studio)"}
                  </button>
                </div>
                <article className="rounded-md bg-paper-card px-8 py-10 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[50vh]">
                  <MarkdownEditor value={draftText} onChange={(v) => { setDraftText(v); setDraftDirty(true); }}
                                  placeholder="Paste or write chapter draft…" />
                </article>
              </div>
            ) : (
              <ProvenancePane
                stage={selected}
                text={stages[selected]}
                canGenerateOutline={hasRegenerateSource(stages)}
                onGenerateOutline={() => startGenerateOutline("text")}
                onGenerateOutlineFromNotes={() => startGenerateOutline("notes")}
                outlineNotes={combinedOutlineInstructions()}
                outlineGenerating={outlineGenerating}
              />
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
      <RenumberChapterModal
        projectId={id}
        chapter={meta ? { number: num, title: meta.title } : { number: num, title: "" }}
        open={renumberOpen}
        onClose={() => setRenumberOpen(false)}
        onDone={(newNum) => navigate(`/projects/${id}/chapters/${newNum}`, { replace: true })}
      />
    </div>
  );
}

function RegeneratePreviewPanel({
  preview, text, onChange, onKeep, onDiscard,
  title = "Regenerated preview",
  keepLabel,
  description,
}: {
  preview: RegeneratePreview;
  text: string;
  onChange: (v: string) => void;
  onKeep: () => void;
  onDiscard: () => void;
  title?: string;
  keepLabel?: string;
  description?: string;
}) {
  const keep = keepLabel ?? `Keep → ${preview.source}`;
  return (
    <section className="mb-8 rounded-xl border border-amber/35 bg-amber/5 p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold text-ink-text">
            {title}
          </h2>
          <p className="mt-1 text-[13px] text-ink-muted">
            {description ?? (
              <>
                From {preview.source} · {preview.original_word_count.toLocaleString()} →{" "}
                {text.split(/\s+/).filter(Boolean).length.toLocaleString()} words.
                Edit below if needed, then keep or discard.
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={onDiscard}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5">
            Discard
          </button>
          <button type="button" onClick={onKeep} disabled={!text.trim()}
                  className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
            {keep}
          </button>
        </div>
      </div>
      <article className="rounded-md bg-paper-card px-6 py-8 shadow-[var(--shadow-paper)] ring-1 ring-paper-line min-h-[240px]">
        <MarkdownEditor value={text} onChange={onChange} placeholder="Generated content…" />
      </article>
    </section>
  );
}

function ProvenancePane({
  stage, text, canGenerateOutline, onGenerateOutline, onGenerateOutlineFromNotes,
  outlineGenerating, outlineNotes,
}: {
  stage: StageKey;
  text: string | null;
  canGenerateOutline?: boolean;
  onGenerateOutline?: () => void;
  onGenerateOutlineFromNotes?: () => void;
  outlineGenerating?: boolean;
  outlineNotes?: string;
}) {
  if (text == null) {
    const hasNotes = Boolean(outlineNotes?.trim());
    return (
      <Empty
        title={`${cap(stage)} not generated yet`}
        hint={
          stage === "outline"
            ? "Enter outline notes (or revision notes with “apply to outline” checked) under the pipeline buttons, then click Outline from notes. If you already have draft prose, use Outline from text instead."
            : "Run the pipeline to produce this stage."
        }
        action={stage === "outline" ? (
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <button type="button" onClick={onGenerateOutlineFromNotes}
                    disabled={outlineGenerating || !hasNotes}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {outlineGenerating ? "Generating…" : "Generate outline from notes"}
            </button>
            {canGenerateOutline && onGenerateOutline && (
              <button type="button" onClick={onGenerateOutline} disabled={outlineGenerating}
                      className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
                {outlineGenerating ? "Generating…" : "Generate outline from chapter text"}
              </button>
            )}
          </div>
        ) : undefined}
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

function Empty({ title, hint, action }: { title: string; hint: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-md bg-paper-card px-11 py-14 text-center shadow-[var(--shadow-paper)] ring-1 ring-paper-line">
      <p className="font-display text-[18px] text-ink-text">{title}</p>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{hint}</p>
      {action}
    </div>
  );
}

function RunButton({
  label, onClick, running, disabled, resume, resumeLabel,
}: {
  label: string; onClick: () => void; running: boolean; disabled?: boolean;
  resume?: boolean; resumeLabel?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 rounded-lg border border-paper-line bg-paper-card px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
    >
      {resume && (
        <ResumeWorkflowDot title={resumeLabel ?? "Last function used on this chapter"} />
      )}
      {running ? "Running…" : label}
    </button>
  );
}

function MineButton({
  label, running, onClick, disabled, resume, resumeLabel,
}: {
  label: string;
  running: boolean;
  onClick: () => void;
  disabled?: boolean;
  resume?: boolean;
  resumeLabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 rounded-lg border border-amber/30 bg-amber/5 px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text transition-colors hover:bg-amber/10 disabled:opacity-40"
    >
      {resume && (
        <ResumeWorkflowDot title={resumeLabel ?? "Last function used on this chapter"} />
      )}
      {running ? "Mining…" : label}
    </button>
  );
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
