import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ProjectDetail, type ChapterSummary, type CharacterSummary } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";
import Outliner from "../components/Outliner";
import Modal, { Field, fieldClass } from "../components/Modal";
import { useToast } from "../components/Toaster";
import { useRunPhase } from "../hooks/useRunPhase";

const ROLE_COLOR: Record<string, string> = {
  protagonist: "var(--color-st-approved)",
  antagonist: "var(--color-st-planned)",
  supporting: "var(--color-st-drafted)",
  minor: "var(--color-ink-muted)",
};

const ROLES = ["protagonist", "antagonist", "supporting", "minor"];

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [characters, setCharacters] = useState<CharacterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [charOpen, setCharOpen] = useState(false);
  const [chapterView, setChapterView] = useState<"board" | "outline">("board");

  const load = useCallback(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
    api.characters(id).then(setCharacters).catch(() => setCharacters([]));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const { run, runningStage, isRunning } = useRunPhase(id, load);

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
          <Action onClick={() => run("plan_outline", { chapters: 12, words: 24000 })}
                  busy={runningStage === "plan_outline"} disabled={isRunning}>
            Plan Outline
          </Action>
          <Action onClick={() => run("plan_chapter", { number: nextChapter })}
                  busy={runningStage === "plan_chapter"} disabled={isRunning}>
            Plan Chapter {nextChapter}
          </Action>
          <a
            href={api.exportUrl(id)}
            download={`${id}.md`}
            className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
          >
            Export
          </a>
          {isRunning && (
            <span className="ml-1 inline-flex items-center gap-2 text-[12.5px] text-ink-muted" aria-live="polite">
              <span className="h-2 w-2 animate-pulse rounded-full bg-amber-deep" />
              Agent running…
            </span>
          )}
        </div>
      </header>

      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Chapters
        </h2>
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
      {chapterView === "board"
        ? <ChapterBoard chapters={chapters} />
        : chapters.length > 0
          ? <Outliner id={id} chapters={chapters} />
          : <ChapterBoard chapters={chapters} />}

      {/* Codex — cast */}
      <div className="mt-12 mb-5 flex items-center justify-between">
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Cast
        </h2>
        <button onClick={() => setCharOpen(true)}
                className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
          + Add Character
        </button>
      </div>
      {characters.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No characters yet. Add your protagonist to begin the codex.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {characters.map((ch) => (
            <div key={ch.id} className="flex items-center gap-3 rounded-xl border border-paper-line bg-paper-card p-4 shadow-[var(--shadow-paper)]">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-display text-[15px] font-semibold text-on-ink"
                    style={{ backgroundColor: ROLE_COLOR[ch.role] ?? "var(--color-ink-muted)" }}>
                {ch.full_name.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0">
                <p className="truncate font-display text-[15px] font-medium text-ink-text">{ch.full_name}</p>
                <p className="text-[12px] capitalize text-ink-muted">{ch.role}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <AddCharacterModal id={id} open={charOpen} onClose={() => setCharOpen(false)} onAdded={load} />
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

function AddCharacterModal({
  id, open, onClose, onAdded,
}: { id: string; open: boolean; onClose: () => void; onAdded: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [role, setRole] = useState("protagonist");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.addCharacter(id, name, role);
      toast(`Added ${name}`, "success");
      setName("");
      onAdded();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Character">
      <form onSubmit={submit}>
        <Field label="Full name">
          <input autoFocus className={fieldClass} value={name}
                 onChange={(e) => setName(e.target.value)} placeholder="e.g. Mara Vale" />
        </Field>
        <Field label="Role">
          <select className={fieldClass} value={role} onChange={(e) => setRole(e.target.value)}
                  style={{ backgroundColor: "var(--color-paper)", color: "var(--color-ink-text)" }}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}</option>
            ))}
          </select>
        </Field>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose}
                  className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5">
            Cancel
          </button>
          <button type="submit" disabled={!name.trim() || busy}
                  className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40">
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
      <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
        {label}
      </div>
    </div>
  );
}
