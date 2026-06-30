import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type EntityDedupStatus, type ProjectDetail, type ChapterSummary, type CharacterSummary, type PlotThreadSummary } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";
import Outliner from "../components/Outliner";
import PlotThreadsPanel from "../components/PlotThreadsPanel";
import DeleteButton from "../components/DeleteButton";
import {
  CharacterEditorModal, GenericImporterPanel, PasteChapterModal, PlotThreadModal,
  QuickAddCharacterModal, RenumberChapterModal, StoryBiblePanel,
} from "../components/CodexEditors";
import ResolveDuplicatesModal from "../components/ResolveDuplicatesModal";
import PlotPanelIssuesModal from "../components/PlotPanelIssuesModal";
import ManualMergeModal, { type MergeKind } from "../components/ManualMergeModal";
import ProjectBackupsModal from "../components/ProjectBackupsModal";
import { useToast } from "../components/Toaster";
import { useConfirm } from "../components/Confirm";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import { useRunPhase } from "../hooks/useRunPhase";
import PanelToggle from "../components/PanelToggle";
import PendingAiStar from "../components/PendingAiStar";
import { ChapterPipelineLegend } from "../components/ChapterPipelineStatus";
import { projectChaptersWithPendingPreviews } from "../lib/chapterPreviewPending";
import { useLayoutPrefs } from "../context/LayoutPrefs";

const ROLE_COLOR: Record<string, string> = {
  protagonist: "var(--color-st-approved)",
  antagonist: "var(--color-st-planned)",
  supporting: "var(--color-st-drafted)",
  minor: "var(--color-ink-muted)",
};

type CodexTab = "importer" | "chapters" | "cast" | "plots" | "bible";

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const toast = useToast();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [plotThreads, setPlotThreads] = useState<PlotThreadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [charOpen, setCharOpen] = useState(false);
  const [dedupOpen, setDedupOpen] = useState(false);
  const [entityDedupStatus, setEntityDedupStatus] = useState<EntityDedupStatus>({
    ai_suggestions_ready: false,
    ai_group_count: 0,
    has_ai_file: false,
    ai_scan_completed: false,
  });
  const [bibleDedupReady, setBibleDedupReady] = useState(false);
  const [previewTick, setPreviewTick] = useState(0);
  const { isProjectJobRunning } = useBackgroundJob();
  const entityScanning = isProjectJobRunning("entity-dedup", id);
  const [plotPanelIssuesOpen, setPlotPanelIssuesOpen] = useState(false);
  const [manualMerge, setManualMerge] = useState<MergeKind | null>(null);
  const [plotMergeMode, setPlotMergeMode] = useState<"parallel" | "nest">("parallel");
  const [dedupKind, setDedupKind] = useState<MergeKind>("character");
  const [backupsOpen, setBackupsOpen] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [editCharId, setEditCharId] = useState<string | null>(null);
  const [plotModal, setPlotModal] = useState<PlotThreadSummary | null | "new">(null);
  const [renumberChapter, setRenumberChapter] = useState<ChapterSummary | null>(null);
  const [codexTab, setCodexTab] = useState<CodexTab>("chapters");
  const [chapterView, setChapterView] = useState<"board" | "outline">("board");

  const load = useCallback(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
    api.characters(id).then(setCharacters).catch(() => setCharacters([]));
    api.plotThreads(id).then(setPlotThreads).catch(() => setPlotThreads([]));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshEntityDedupStatus = useCallback(() => {
    api.duplicatesStatus(id).then(setEntityDedupStatus).catch(() => {
      setEntityDedupStatus({
        ai_suggestions_ready: false,
        ai_group_count: 0,
        has_ai_file: false,
        ai_scan_completed: false,
      });
    });
  }, [id]);

  useEffect(() => { refreshEntityDedupStatus(); }, [refreshEntityDedupStatus]);

  useEffect(() => {
    api.bibleDedupStatus(id).then((s) => setBibleDedupReady(s.ai_suggestions_ready)).catch(() => setBibleDedupReady(false));
  }, [id, dedupOpen, codexTab]);

  useEffect(() => {
    const bump = () => setPreviewTick((n) => n + 1);
    window.addEventListener("novel-os:preview-pending", bump);
    return () => window.removeEventListener("novel-os:preview-pending", bump);
  }, []);

  const chapterPreviewPending = projectChaptersWithPendingPreviews(id).size > 0;
  void previewTick;

  function openDedup(kind: MergeKind) {
    setDedupKind(kind);
    setDedupOpen(true);
  }

  function dedupBadge() {
    if (entityScanning) return <span className="ml-1.5 rounded-full bg-amber/25 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-deep">scanning</span>;
    if (entityDedupStatus.ai_suggestions_ready) {
      const plotOnly = entityDedupStatus.plot_thread_group_count ?? 0;
      const label = plotOnly > 0 && (entityDedupStatus.character_group_count ?? 0) === 0
        ? `${plotOnly} plot AI`
        : `${entityDedupStatus.ai_group_count} AI`;
      return (
        <span className="ml-1.5 rounded-full bg-amber/25 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-deep">
          {label}
        </span>
      );
    }
    if (entityDedupStatus.ai_scan_completed) {
      return (
        <span className="ml-1.5 rounded-full bg-ink/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-muted">
          AI done
        </span>
      );
    }
    return null;
  }

  const { showLibrary, toggleLibrary } = useLayoutPrefs();
  const { run, runningStage, isRunning } = useRunPhase(id, load);

  async function deleteChapter(c: ChapterSummary) {
    try {
      await api.deleteChapter(id, c.number);
      toast(`Deleted chapter ${c.number}`, "success");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function deleteCharacter(ch: CharacterSummary) {
    try {
      await api.deleteCharacter(id, ch.id);
      toast(`Removed ${ch.full_name}`, "success");
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function deleteProject() {
    if (!project) return;
    const ok = await confirm({
      title: "Delete manuscript",
      message: `Permanently delete "${project.title}" and everything in it? This cannot be undone.`,
      confirmLabel: "Delete manuscript",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteProject(id);
      toast(`Deleted "${project.title}"`, "success");
      navigate("/");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  if (error)
    return (
      <div className="px-10 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load: {error}
        </div>
      </div>
    );
  if (!project)
    return (
      <div className="mx-auto max-w-5xl px-10 py-12">
        <div className="h-3.5 w-24 animate-pulse rounded bg-paper-card" />
        <div className="mt-4 h-10 w-2/3 animate-pulse rounded bg-paper-card" />
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-paper-card" />
          ))}
        </div>
      </div>
    );

  const words = chapters.reduce((s, c) => s + c.word_count, 0);
  const drafted = chapters.filter((c) => c.status !== "planned").length;
  const nextChapter = chapters.length ? Math.max(...chapters.map((c) => c.number)) + 1 : 1;

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-amber-deep"
      >
        ← Library
      </Link>

      <header className="mb-9 border-b border-paper-line pb-8">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.18em] text-amber-deep">
          {project.genre}
        </p>
        <h1 className="font-display text-[38px] font-semibold leading-tight tracking-tight text-ink-text text-balance">
          {project.title}
        </h1>
        <p className="mt-2 text-[14px] text-ink-muted">by {project.author || "Unknown"}</p>

        <div className="mt-7 flex flex-wrap gap-8">
          <Stat label="Chapters" value={String(project.chapter_count)} />
          <Stat label="Written" value={`${drafted}/${project.chapter_count || 0}`} />
          <Stat label="Words" value={words.toLocaleString()} />
        </div>

        <div className="mt-7 flex flex-wrap items-center gap-2.5">
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            <PanelToggle on={showLibrary} onClick={toggleLibrary} label="Library" />
          </div>
          <Action onClick={() => setPasteOpen(true)} variant="primary">
            + Paste Chapter
          </Action>
          <Action onClick={() => setCodexTab("importer")}>
            Generic Importer
          </Action>
          <Action onClick={() => run("plan_outline", { chapters: 12, words: 24000 })}
                  busy={runningStage === "plan_outline"} disabled={isRunning}>
            Plan Outline
          </Action>
          <Action onClick={() => run("plan_chapter", { number: nextChapter })}
                  busy={runningStage === "plan_chapter"} disabled={isRunning}>
            Plan Chapter {nextChapter}
          </Action>
          <Action onClick={() => setBackupsOpen(true)}>
            Backups
          </Action>
          <a
            href={api.exportUrl(id)}
            download={`${id}.md`}
            className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
          >
            Export manuscript
          </a>
          <a
            href={api.exportProjectPackageUrl(id)}
            download
            className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
          >
            Export project
          </a>
          <button
            type="button"
            onClick={deleteProject}
            className="rounded-lg border border-red-200 px-4 py-2 text-[13px] font-semibold text-red-600 transition-colors hover:bg-red-50"
          >
            Delete Manuscript
          </button>
          {isRunning && (
            <span className="ml-1 inline-flex items-center gap-2 text-[12.5px] text-ink-muted" aria-live="polite">
              <span className="h-2 w-2 animate-pulse rounded-full bg-amber-deep" />
              Agent running…
            </span>
          )}
        </div>
      </header>

      <div className="mb-8 flex gap-1 overflow-x-auto border-b border-paper-line pb-px">
        {([
          ["importer", "Generic Importer"],
          ["chapters", "Chapters"],
          ["cast", "Cast"],
          ["plots", "Plot Threads"],
          ["bible", "Story Bible"],
        ] as const).map(([tab, label]) => (
          <button key={tab} onClick={() => setCodexTab(tab)}
                  className={`shrink-0 px-4 py-2.5 text-[13px] font-semibold transition-colors ${
                    codexTab === tab
                      ? "border-b-2 border-amber-deep text-ink-text"
                      : "text-ink-muted hover:text-ink-text"
                  }`}>
            {label}
            {tab === "chapters" && chapterPreviewPending && (
              <PendingAiStar title="Chapter AI preview ready to review" />
            )}
            {tab === "cast" && entityDedupStatus.ai_suggestions_ready
              && (entityDedupStatus.character_group_count ?? entityDedupStatus.ai_group_count) > 0 && (
              <PendingAiStar title="Character dedup results ready" />
            )}
            {tab === "plots" && entityDedupStatus.ai_suggestions_ready
              && (entityDedupStatus.plot_thread_group_count ?? 0) > 0 && (
              <PendingAiStar title="Plot dedup results ready" />
            )}
            {tab === "bible" && bibleDedupReady && (
              <PendingAiStar title="Story bible dedup results ready" />
            )}
          </button>
        ))}
      </div>

      {codexTab === "importer" && (
        <GenericImporterPanel projectId={id} onExtracted={load} />
      )}

      {codexTab === "chapters" && (
      <>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
            Chapters
          </h2>
          <div className="mt-2">
            <ChapterPipelineLegend compact />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setPasteOpen(true)}
                  className="rounded-lg border border-paper-line px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5">
            + Paste Chapter
          </button>
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
          {(["board", "outline"] as const).map((v) => (
            <button key={v} onClick={() => setChapterView(v)}
                    className={`px-3.5 py-1.5 text-[12.5px] font-medium capitalize transition-colors ${
                      chapterView === v ? "bg-ink text-on-ink" : "text-ink-muted hover:bg-ink/5"}`}>
              {v === "outline" ? "Outliner" : "Board"}
            </button>
          ))}
          </div>
        </div>
      </div>
      {chapterView === "board"
        ? <ChapterBoard chapters={chapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />
        : chapters.length > 0
          ? <Outliner id={id} chapters={chapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />
          : <ChapterBoard chapters={chapters} onDelete={deleteChapter} onRenumber={setRenumberChapter} />}
      </>
      )}

      {codexTab === "cast" && (
      <>
      {/* Codex — cast */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Cast
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={() => setManualMerge("character")}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            Merge manually…
          </button>
          <button onClick={() => openDedup("character")}
                  className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-amber/10">
            Resolve duplicates{dedupBadge()}
            {entityDedupStatus.ai_suggestions_ready && !entityScanning && (
              <PendingAiStar title="AI dedup results ready to review" />
            )}
          </button>
          <button onClick={() => setCharOpen(true)}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            + Add Character
          </button>
        </div>
      </div>
      {characters.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No characters yet. Use <button type="button" onClick={() => setCodexTab("importer")} className="font-semibold text-amber-deep underline-offset-2 hover:underline">Generic Importer</button> or add manually.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((ch) => (
            <button key={ch.id} type="button" onClick={() => setEditCharId(ch.id)}
                    className="group relative flex items-center gap-3 rounded-xl border border-paper-line bg-paper-card p-4 text-left shadow-[var(--shadow-paper)] transition-colors hover:border-amber/40">
              <DeleteButton
                label={`Delete ${ch.full_name}`}
                title="Delete character"
                message={`Remove ${ch.full_name} from the cast?`}
                onConfirm={() => deleteCharacter(ch)}
                className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
              />
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-display text-[15px] font-semibold text-on-ink"
                    style={{ backgroundColor: ROLE_COLOR[ch.role] ?? "var(--color-ink-muted)" }}>
                {ch.full_name.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 pr-6">
                <p className="truncate font-display text-[15px] font-medium text-ink-text">{ch.full_name}</p>
                <p className="text-[12px] capitalize text-ink-muted">{ch.role}</p>
                {ch.aliases && ch.aliases.length > 0 && (
                  <p className="truncate text-[11px] text-ink-muted/80">
                    aka {ch.aliases.slice(0, 3).join(", ")}{ch.aliases.length > 3 ? "…" : ""}
                  </p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
      </>
      )}

      {codexTab === "plots" && (
      <>
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Plot Threads
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={() => { setPlotMergeMode("parallel"); setManualMerge("plot_thread"); }}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            Merge manually…
          </button>
          <button onClick={() => { setPlotMergeMode("nest"); setManualMerge("plot_thread"); }}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            Nest as subplots…
          </button>
          <button type="button" onClick={() => setPlotPanelIssuesOpen(true)}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            Check subplot issues
          </button>
          <button onClick={() => openDedup("plot_thread")}
                  className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-amber/10">
            Resolve duplicates{dedupBadge()}
            {entityDedupStatus.ai_suggestions_ready && !entityScanning && (
              <PendingAiStar title="AI dedup results ready to review" />
            )}
          </button>
          <button onClick={() => setPlotModal("new")}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
            + Add Plot Thread
          </button>
        </div>
      </div>
      {plotThreads.length === 0 ? (
        <PlotThreadsPanel projectId={id} threads={[]} onChange={load} onAdd={() => setPlotModal("new")} />
      ) : (
        <PlotThreadsPanel projectId={id} threads={plotThreads} onChange={load} onAdd={() => setPlotModal("new")} />
      )}
      </>
      )}

      {codexTab === "bible" && (
        <StoryBiblePanel projectId={id} />
      )}

      {!dedupOpen && entityScanning && (
        <p className="fixed bottom-4 right-4 z-40 max-w-sm rounded-lg border border-amber/30 bg-paper-card px-4 py-2 text-[12.5px] text-ink-text shadow-[var(--shadow-lift)]">
          Duplicate AI scan running —{" "}
          <button type="button" onClick={() => setDedupOpen(true)} className="font-semibold text-amber-deep underline-offset-2 hover:underline">
            open resolve duplicates
          </button>
        </p>
      )}

      <PasteChapterModal projectId={id} open={pasteOpen} onClose={() => setPasteOpen(false)}
                         onDone={load} defaultNumber={nextChapter} />
      <QuickAddCharacterModal projectId={id} open={charOpen} onClose={() => setCharOpen(false)}
                              onAdded={(c) => { load(); setEditCharId(c.id); }} />
      <CharacterEditorModal projectId={id} characterId={editCharId} open={editCharId != null}
                            onClose={() => setEditCharId(null)} onSaved={load} />
      <PlotThreadModal projectId={id} thread={plotModal === "new" ? null : plotModal}
                       open={plotModal != null} onClose={() => setPlotModal(null)} onSaved={load} />
      <RenumberChapterModal projectId={id} chapter={renumberChapter}
                           open={renumberChapter != null} onClose={() => setRenumberChapter(null)}
                           onDone={(n) => { load(); navigate(`/projects/${id}/chapters/${n}`); }} />
      <ResolveDuplicatesModal projectId={id} open={dedupOpen} onClose={() => setDedupOpen(false)}
                                onDone={load} defaultKind={dedupKind} onStatusChange={refreshEntityDedupStatus} />
      <PlotPanelIssuesModal projectId={id} open={plotPanelIssuesOpen} onClose={() => setPlotPanelIssuesOpen(false)}
                              onDone={load} />
      {manualMerge != null && (
        <ManualMergeModal projectId={id} kind={manualMerge} open
                          defaultPlotMode={manualMerge === "plot_thread" ? plotMergeMode : "parallel"}
                          onClose={() => setManualMerge(null)} onDone={load} />
      )}
      {backupsOpen && (
        <ProjectBackupsModal projectId={id} open onClose={() => setBackupsOpen(false)} onDone={load} />
      )}
    </div>
  );
}

function Action({
  children, onClick, busy, disabled, variant = "primary",
}: {
  children: React.ReactNode; onClick: () => void; busy?: boolean; disabled?: boolean;
  variant?: "primary" | "ghost";
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        variant === "primary"
          ? "rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          : "rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
      }
    >
      {busy ? "Running…" : children}
    </button>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="nums font-display text-[26px] font-semibold leading-none text-ink-text">
        {value}
      </div>
      <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
        {label}
      </div>
    </div>
  );
}
