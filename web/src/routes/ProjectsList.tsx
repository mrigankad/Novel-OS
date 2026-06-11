import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { api, type ProjectSummary } from "../api/client";
import ProjectCard from "../components/ProjectCard";
import Modal, { Field, fieldClass } from "../components/Modal";
import { useToast } from "../components/Toaster";

const grid = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } };
const card = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } },
};

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-10 py-12">
      <header className="mb-10 flex items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.2em] text-amber-deep">
            Library
          </p>
          <h1 className="font-display text-[40px] font-semibold leading-none tracking-tight text-ink-text text-balance">
            Your manuscripts
          </h1>
          <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-muted">
            Every project is a living workspace — outlines, drafts, characters and continuity,
            orchestrated by your agent pipeline.
          </p>
        </div>
        <button
          onClick={() => setOpen(true)}
          className="shrink-0 rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800"
        >
          + New Manuscript
        </button>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
          Failed to load projects: {error}
        </div>
      )}

      {!error && !projects && <SkeletonGrid />}

      {!error && projects && projects.length === 0 && (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-14 text-center">
          <p className="font-display text-[20px] text-ink-text">No manuscripts yet</p>
          <p className="mt-2 text-[14px] text-ink-muted">
            Start your first one — it takes a title and a genre.
          </p>
          <button
            onClick={() => setOpen(true)}
            className="mt-5 rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800"
          >
            + New Manuscript
          </button>
        </div>
      )}

      {projects && projects.length > 0 && (
        <motion.div
          variants={grid}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          {projects.map((p) => (
            <motion.div key={p.id} variants={card}>
              <ProjectCard p={p} />
            </motion.div>
          ))}
        </motion.div>
      )}

      <NewProjectModal open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const p = await api.createProject({ title, genre, author });
      toast("Manuscript created", "success");
      navigate(`/projects/${p.id}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New Manuscript">
      <form onSubmit={create}>
        <Field label="Title">
          <input
            autoFocus
            className={fieldClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. The Last Signal"
          />
        </Field>
        <Field label="Genre">
          <input
            className={fieldClass}
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="e.g. Sci-Fi Thriller"
          />
        </Field>
        <Field label="Author">
          <input
            className={fieldClass}
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Your name"
            autoComplete="name"
          />
        </Field>
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!title.trim() || busy}
            className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-44 animate-pulse rounded-xl border border-paper-line bg-paper-card/70"
        />
      ))}
    </div>
  );
}
