import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import {
  api,
  type CodexEntry,
  type CodexEntryType,
  type ContinuityReport,
  type ProjectDetail,
  type ChapterSummary,
  type RelationshipEdge,
} from "../api/client";
import ChapterBoard from "../components/ChapterBoard";
import { badgesFromFindings } from "../lib/chapterBadges";
import Outliner from "../components/Outliner";
import WritingTargets from "../components/WritingTargets";
import ManuscriptStats from "../components/ManuscriptStats";
import CollectionsPanel from "../components/CollectionsPanel";
import Modal, { Field, fieldClass, textareaClass } from "../components/Modal";
import Scene from "../components/Scene";
import ChoiceGroup from "../components/ChoiceGroup";
import AddRelationshipModal from "../components/AddRelationshipModal";
import Icon from "../components/Icon";
import CodexImageButton from "../components/CodexImageButton";
import { useToast } from "../components/toastContext";
import { useRunPhase } from "../hooks/useRunPhase";
import type { IconName } from "../icons/registry";

const ROLE_OPTIONS = (["protagonist", "antagonist", "supporting", "minor"] as const).map((r) => ({
  value: r,
  label: r[0].toUpperCase() + r.slice(1),
}));

const CODEX_FILTERS: { id: "all" | CodexEntryType; label: string; icon: IconName }[] = [
  { id: "all", label: "All", icon: "layers" },
  { id: "character", label: "Characters", icon: "users" },
  { id: "location", label: "Locations", icon: "map-pin" },
  { id: "worldbuilding", label: "World", icon: "landmark" },
  { id: "item", label: "Items", icon: "package" },
];

const TYPE_OPTIONS: { value: CodexEntryType; label: string; icon: IconName; hint: string }[] = [
  { value: "character", label: "Character", icon: "users", hint: "People" },
  { value: "location", label: "Location", icon: "map-pin", hint: "Places" },
  { value: "worldbuilding", label: "World", icon: "landmark", hint: "Systems" },
  { value: "item", label: "Item", icon: "package", hint: "Objects" },
];

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const focusCodexId = searchParams.get("codex");
  const toast = useToast();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [codex, setCodex] = useState<CodexEntry[]>([]);
  const [edges, setEdges] = useState<RelationshipEdge[]>([]);
  const [continuity, setContinuity] = useState<ContinuityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entryOpen, setEntryOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkSource, setLinkSource] = useState<string | undefined>();
  const [codexFilter, setCodexFilter] = useState<"all" | CodexEntryType>("all");
  const [chapterView, setChapterView] = useState<"board" | "outline">("board");

  const load = useCallback(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
    api.codex(id).then(setCodex).catch(() => setCodex([]));
    api.relationships(id).then(setEdges).catch(() => setEdges([]));
    api.continuity(id).then(setContinuity).catch(() => setContinuity(null));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Deep link (?codex=…) switches the filter to that entry's type. Adjusted
  // during render so the entry is already on screen when we scroll to it.
  const focusEntry = focusCodexId ? codex.find((e) => e.id === focusCodexId) : undefined;
  const [lastFocus, setLastFocus] = useState<string | undefined>(undefined);
  if (focusEntry && focusEntry.id !== lastFocus) {
    setLastFocus(focusEntry.id);
    setCodexFilter(focusEntry.entry_type);
  }

  useEffect(() => {
    if (!focusCodexId || codex.length === 0) return;
    const el = document.getElementById(`codex-${focusCodexId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusCodexId, codex]);

  const { run, runningStage, isRunning } = useRunPhase(id, load);

  const filtered = useMemo(
    () => (codexFilter === "all" ? codex : codex.filter((e) => e.entry_type === codexFilter)),
    [codex, codexFilter],
  );
  const characters = useMemo(
    () => codex.filter((e) => e.entry_type === "character"),
    [codex],
  );

  if (error)
    return (
      <Scene>
        <div className="px-10 py-12">
          <div className="glass-panel px-4 py-3 text-[13px] text-ink-text">
            Failed to load: {error}
          </div>
        </div>
      </Scene>
    );
  if (!project)
    return (
      <Scene>
        <div className="mx-auto max-w-5xl px-6 py-12 sm:px-10">
          <div className="glass-shell p-4">
            <div className="glass-panel p-8">
              <div className="h-3.5 w-24 animate-pulse rounded bg-white/50" />
              <div className="mt-4 h-10 w-2/3 animate-pulse rounded bg-white/50" />
              <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-28 animate-pulse rounded-2xl bg-white/40" />
                ))}
              </div>
            </div>
          </div>
        </div>
      </Scene>
    );

  const words = chapters.reduce((s, c) => s + c.word_count, 0);
  const drafted = chapters.filter((c) => c.status !== "planned").length;
  const nextChapter = chapters.length ? Math.max(...chapters.map((c) => c.number)) + 1 : 1;

  return (
    <Scene>
      <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
        <motion.div
          initial={{ opacity: 0, y: 18, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.45, ease: [0.2, 0.8, 0.2, 1] }}
          className="glass-shell p-3 sm:p-4"
        >
          <div className="glass-panel px-6 py-8 sm:px-10 sm:py-10">
            <Link
              to="/"
              className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-[var(--color-violet)]"
            >
              ← Library
            </Link>

            <header className="mb-9">
              <p className="eyebrow">{project.genre}</p>
              <h1 className="font-display text-[32px] font-semibold leading-tight tracking-[-0.035em] text-ink-text text-balance sm:text-[38px]">
                {project.title}
              </h1>
              <p className="mt-2 text-[14px] text-ink-muted">by {project.author || "Unknown"}</p>
              {project.premise ? (
                <p className="mt-3 max-w-2xl text-[13.5px] leading-relaxed text-ink-muted">
                  {project.premise}
                </p>
              ) : null}

              <div className="mt-7 flex flex-wrap gap-8">
                <Stat label="Chapters" value={String(project.chapter_count)} />
                <Stat label="Written" value={`${drafted}/${project.chapter_count || 0}`} />
                <Stat label="Words" value={words.toLocaleString()} />
              </div>

              <div className="mt-7 flex flex-wrap items-center gap-2.5">
                <Action onClick={() => run("plan_outline", { chapters: 12, words: 24000 })}
                        busy={runningStage === "plan_outline"} disabled={isRunning}>
                  Plan Outline
                </Action>
                <Action onClick={() => run("plan_chapter", { number: nextChapter })}
                        busy={runningStage === "plan_chapter"} disabled={isRunning}>
                  Plan Chapter {nextChapter}
                </Action>
                <a href={api.exportUrl(id)} download={`${id}.md`} className="btn-secondary">
                  Export
                </a>
                <ChoiceGroup
                  label="Content rating"
                  variant="segmented"
                  size="sm"
                  value={(project.content_rating === "mature" ? "mature" : "general") as "general" | "mature"}
                  onChange={async (next) => {
                    try {
                      const p = await api.updateProject(id, { content_rating: next });
                      setProject(p);
                      toast(next === "mature" ? "Marked Mature" : "Marked General", "success");
                    } catch (e) {
                      toast(e instanceof Error ? e.message : String(e), "error");
                    }
                  }}
                  options={[
                    { value: "general", label: "General" },
                    { value: "mature", label: "Mature" },
                  ]}
                />
                {isRunning && (
                  <span className="ml-1 inline-flex items-center gap-2 text-[12.5px] text-ink-muted" aria-live="polite">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--color-violet)]" />
                    Agent running…
                  </span>
                )}
              </div>
            </header>

            <WritingTargets
              projectId={id}
              project={project}
              wordCount={words}
              onUpdated={setProject}
            />

            <ManuscriptStats projectId={id} />

            <ContinuityHealth report={continuity} onRefresh={() => {
              api.continuity(id).then(setContinuity).catch(() => setContinuity(null));
            }} />

            <div className="mt-6">
              <CollectionsPanel projectId={id} />
            </div>

            <div className="mb-5 mt-10 flex items-center justify-between">
              <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
                Chapters
              </h2>
              <div className="flex overflow-hidden rounded-full border border-[rgba(96,112,153,0.16)] bg-white/45 p-0.5">
                {(["board", "outline"] as const).map((v) => (
                  <button key={v} type="button" onClick={() => setChapterView(v)}
                          className={`rounded-full px-3.5 py-1.5 text-[12.5px] font-medium capitalize transition-colors ${
                            chapterView === v
                              ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                              : "text-ink-muted hover:text-ink"}`}>
                    {v === "outline" ? "Outliner" : "Corkboard"}
                  </button>
                ))}
              </div>
            </div>
            {chapterView === "board"
              ? <ChapterBoard chapters={chapters} continuityBadges={badgesFromFindings(continuity?.findings)} />
              : chapters.length > 0
                ? <Outliner id={id} chapters={chapters} />
                : <ChapterBoard chapters={chapters} continuityBadges={badgesFromFindings(continuity?.findings)} />}

            <div className="mt-12 mb-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
                  Codex
                </h2>
                <p className="mt-1 text-[13px] text-ink-muted">
                  Click an avatar to add a portrait, place photo, or item image.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/projects/${id}/research`} className="btn-ghost inline-flex items-center gap-1.5">
                  <Icon name="image" className="h-3.5 w-3.5" /> Research
                </Link>
                <Link to={`/projects/${id}/chart`} className="btn-ghost inline-flex items-center gap-1.5">
                  <Icon name="waypoints" className="h-3.5 w-3.5" /> Chart
                </Link>
                <button type="button" onClick={() => setEntryOpen(true)} className="btn-secondary">
                  + Add Entry
                </button>
              </div>
            </div>

            <div className="mb-4 flex flex-wrap gap-1.5">
              {CODEX_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setCodexFilter(f.id)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                    codexFilter === f.id
                      ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                      : "bg-white/55 text-ink-muted hover:text-ink"
                  }`}
                >
                  <Icon name={f.icon} className="h-3.5 w-3.5" />
                  {f.label}
                </button>
              ))}
            </div>

            {filtered.length === 0 ? (
              <div className="rounded-[24px] border border-dashed border-[rgba(74,91,133,0.18)] bg-white/45 px-8 py-10 text-center text-[13.5px] text-ink-muted">
                No entries yet. Add characters, places, and world rules the Guardian can check against.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {filtered.map((entry) => (
                  <div
                    key={`${entry.entry_type}-${entry.id}`}
                    id={`codex-${entry.id}`}
                    className={focusCodexId === entry.id ? "rounded-[28px] ring-2 ring-[rgba(104,103,234,0.45)]" : undefined}
                  >
                  <CodexCard
                    projectId={id}
                    entry={entry}
                    edges={edges.filter(
                      (e) => e.source_id === entry.id || e.target_id === entry.id,
                    )}
                    onUpdated={load}
                    onAddLink={
                      entry.entry_type === "character"
                        ? () => {
                            setLinkSource(entry.id);
                            setLinkOpen(true);
                          }
                        : undefined
                    }
                  />
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </div>

      <AddCodexModal id={id} open={entryOpen} onClose={() => setEntryOpen(false)} onAdded={load} />
      <AddRelationshipModal
        open={linkOpen}
        onClose={() => { setLinkOpen(false); setLinkSource(undefined); }}
        characters={characters}
        projectId={id}
        onAdded={load}
        prefill={linkSource ? { source: linkSource } : null}
      />
    </Scene>
  );
}

function ContinuityHealth({
  report, onRefresh,
}: { report: ContinuityReport | null; onRefresh: () => void }) {
  const critical = report?.critical ?? 0;
  const warning = report?.warning ?? 0;
  const info = report?.info ?? 0;
  const total = report?.findings.length ?? 0;
  const healthy = report != null && critical === 0 && warning === 0;

  return (
    <div className="rounded-[24px] border border-[rgba(74,91,133,0.12)] bg-white/55 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
            !report ? "bg-white/70 text-ink-muted"
              : critical > 0 ? "bg-[#ffeaf1] text-[#c85177]"
                : warning > 0 ? "bg-[#fff2dc] text-[#c47a1b]"
                  : "bg-[#e9f7ef] text-[#2f8a57]"
          }`}>
            <Icon
              name={!report ? "shield" : critical > 0 ? "shield-alert" : healthy ? "circle-check" : "triangle-alert"}
              className="h-4 w-4"
            />
          </span>
          <div>
            <h3 className="font-display text-[17px] font-semibold tracking-tight text-ink-text">
              Continuity health
            </h3>
            <p className="mt-0.5 text-[13px] text-ink-muted">
              {!report
                ? "Running deterministic checks…"
                : healthy
                  ? total === 0
                    ? "No findings story bible looks consistent."
                    : `${info} informational note${info === 1 ? "" : "s"}; no blockers.`
                  : `${critical} critical · ${warning} warning · ${info} info`}
            </p>
          </div>
        </div>
        <button type="button" onClick={onRefresh} className="btn-ghost text-[12.5px]">
          Refresh
        </button>
      </div>
      {report && report.findings.length > 0 && (
        <ul className="mt-4 space-y-2">
          {report.findings.slice(0, 4).map((f, i) => (
            <li key={`${f.category}-${i}`} className="flex gap-2 text-[13px] text-ink-text">
              <Icon
                name={f.severity === "critical" ? "circle-alert" : f.severity === "warning" ? "triangle-alert" : "circle-check"}
                className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-muted"
              />
              <span>
                <span className="capitalize text-ink-muted">{f.severity}</span>
                {" · "}
                {f.message}
              </span>
            </li>
          ))}
          {report.findings.length > 4 && (
            <li className="text-[12.5px] text-ink-muted">
              +{report.findings.length - 4} more open Notes → Continuity on a chapter.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function CodexCard({
  projectId, entry, edges, onUpdated, onAddLink,
}: {
  projectId: string;
  entry: CodexEntry;
  edges: RelationshipEdge[];
  onUpdated: () => void;
  onAddLink?: () => void;
}) {
  const toast = useToast();
  const typeIcon: IconName =
    entry.entry_type === "location" ? "map-pin"
      : entry.entry_type === "worldbuilding" ? "landmark"
        : entry.entry_type === "item" ? "package"
          : "users";
  const isPerson = entry.entry_type === "character";

  return (
    <div className={`glass-card flex gap-3 p-4 ${isPerson ? "flex-col" : "items-center"}`}>
      <div className={`flex gap-3 ${isPerson ? "sm:flex-row sm:items-center" : "items-center"}`}>
        <CodexImageButton
          projectId={projectId}
          entry={entry}
          onUpdated={onUpdated}
          size={isPerson ? "lg" : "md"}
          shape={isPerson || entry.entry_type === "location" ? (isPerson ? "circle" : "rounded") : "rounded"}
          label={
            entry.entry_type === "location" ? "Place photo"
              : entry.entry_type === "item" ? "Item image"
                : entry.entry_type === "worldbuilding" ? "Reference"
                  : "Portrait"
          }
        />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-[15px] font-medium text-ink-text">{entry.name}</p>
          <p className="mt-0.5 flex items-center gap-1 text-[12px] capitalize text-ink-muted">
            <Icon name={typeIcon} className="h-3 w-3" />
            {entry.entry_type === "worldbuilding" ? "World" : entry.entry_type}
            {entry.role ? ` · ${entry.role}` : ""}
          </p>
          {entry.summary ? (
            <p className="mt-1 line-clamp-2 text-[12px] text-ink-muted">{entry.summary}</p>
          ) : null}
        </div>
      </div>

      {isPerson && (
        <div className="border-t border-[rgba(74,91,133,0.1)] pt-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-[11.5px] font-medium tracking-[-0.01em] text-ink-muted">Connections</p>
            {onAddLink && (
              <button type="button" onClick={onAddLink} className="btn-ghost px-2 py-0.5 text-[11.5px]">
                + Link
              </button>
            )}
          </div>
          {edges.length === 0 ? (
            <p className="text-[12px] text-paper-muted">No bonds yet</p>
          ) : (
            <ul className="space-y-1.5">
              {edges.slice(0, 4).map((e) => {
                const other =
                  e.source_id === entry.id
                    ? (e.target_name || e.target_id)
                    : (e.source_name || e.source_id);
                return (
                  <li key={e.id} className="flex items-center justify-between gap-2 text-[12.5px]">
                    <span className="min-w-0 truncate text-ink-text">
                      <span className="capitalize text-ink-muted">{e.label}</span>
                      {" · "}
                      <span className="font-medium">{other}</span>
                    </span>
                    <button
                      type="button"
                      className="shrink-0 text-[11px] text-ink-muted hover:text-[#c85177]"
                      aria-label={`Remove link to ${other}`}
                      onClick={async () => {
                        try {
                          await api.deleteRelationship(projectId, e.id);
                          toast("Link removed", "success");
                          onUpdated();
                        } catch (err) {
                          toast(err instanceof Error ? err.message : String(err), "error");
                        }
                      }}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
              {edges.length > 4 && (
                <li className="text-[11.5px] text-ink-muted">+{edges.length - 4} more on Chart</li>
              )}
            </ul>
          )}
        </div>
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
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={variant === "primary" ? "btn-primary disabled:opacity-40" : "btn-secondary disabled:opacity-40"}
    >
      {busy ? "Running…" : children}
    </button>
  );
}

function AddCodexModal({
  id, open, onClose, onAdded,
}: { id: string; open: boolean; onClose: () => void; onAdded: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [entryType, setEntryType] = useState<CodexEntryType>("character");
  const [role, setRole] = useState("protagonist");
  const [summary, setSummary] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pickFile(f: File | undefined) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const list = await api.addCodexEntry(id, {
        entry_type: entryType,
        name: name.trim(),
        role,
        summary: summary.trim(),
      });
      const created = list.find(
        (x) => x.name.toLowerCase() === name.trim().toLowerCase() && x.entry_type === entryType,
      ) ?? list[list.length - 1];
      if (file && created) {
        const kind = entryType === "location" ? "location" : entryType === "character" ? "portrait" : "general";
        const media = await api.uploadMedia(id, file, kind, name.trim());
        await api.setPortrait(id, created.id, media.id, entryType);
      }
      toast(`Added ${name}`, "success");
      setName("");
      setSummary("");
      setFile(null);
      setPreview(null);
      onAdded();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Codex Entry">
      <form onSubmit={submit}>
        <Field label="Type">
          <ChoiceGroup
            label="Type"
            variant="cards"
            value={entryType}
            onChange={setEntryType}
            options={TYPE_OPTIONS}
          />
        </Field>
        <Field label="Name">
          <input autoFocus className={fieldClass} value={name}
                 onChange={(e) => setName(e.target.value)} placeholder="e.g. Mara Vale" />
        </Field>
        {entryType === "character" && (
          <Field label="Role">
            <ChoiceGroup
              label="Role"
              variant="chips"
              value={role}
              onChange={setRole}
              options={ROLE_OPTIONS}
            />
          </Field>
        )}
        {entryType !== "character" && (
          <Field label="Summary">
            <textarea
              className={`${textareaClass} min-h-[72px]`}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="One or two sentences the Guardian can check against"
            />
          </Field>
        )}
        <Field label="Image (optional)">
          <div className="flex items-center gap-3">
            <label className="flex h-16 w-16 cursor-pointer items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[rgba(74,91,133,0.25)] bg-white/50 text-ink-muted hover:border-[var(--color-violet)]">
              {preview ? (
                <img src={preview} alt="" className="h-full w-full object-cover" />
              ) : (
                <Icon name="image" className="h-5 w-5" />
              )}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                className="hidden"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
            </label>
            <p className="text-[12.5px] text-ink-muted">
              {entryType === "character" ? "Character portrait"
                : entryType === "location" ? "Place photo"
                  : "Reference image"}
              . You can add or change this later on the card.
            </p>
          </div>
        </Field>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-ghost">
            Cancel
          </button>
          <button type="submit" disabled={!name.trim() || busy} className="btn-primary disabled:opacity-40">
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="nums font-display text-[26px] font-semibold leading-none text-ink-text">
        {value}
      </div>
      <div className="mt-1 text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
        {label}
      </div>
    </div>
  );
}
