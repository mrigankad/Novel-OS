import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { api, type ProjectSummary, type StudioLlmStatus } from "../api/client";
import ProjectCard from "../components/ProjectCard";
import Modal, { Field, fieldClass, textareaClass } from "../components/Modal";
import Scene from "../components/Scene";
import Icon from "../components/Icon";
import GenreChips from "../components/GenreChips";
import { mergeGenres } from "../lib/genres";
import { useToast } from "../components/toastContext";

const grid = { hidden: {}, show: { transition: { staggerChildren: 0.045 } } };
const card = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.2, 0.8, 0.2, 1] as const } },
};

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [llm, setLlm] = useState<StudioLlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [sampleBusy, setSampleBusy] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
    api.studioLlm().then(setLlm).catch(() => setLlm(null));
  }, []);

  async function dismissOnboarding() {
    try {
      const next = await api.updateStudioLlm({ onboarding_completed: true });
      setLlm(next);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function openSample() {
    setSampleBusy(true);
    try {
      const p = await api.createSampleProject();
      await api.updateStudioLlm({ onboarding_completed: true }).then(setLlm).catch(() => undefined);
      toast("Sample manuscript ready", "success");
      navigate(`/projects/${p.id}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      setSampleBusy(false);
    }
  }

  const showWelcome = llm && (!llm.onboarding_completed || !llm.configured);

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
            <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Your workspace</p>
                <h1 className="font-display text-[32px] font-semibold leading-none tracking-[-0.035em] text-ink-text sm:text-[36px]">
                  Manuscripts
                </h1>
                <p className="mt-3 max-w-lg text-[14px] leading-relaxed text-ink-muted">
                  Projects, chapters, and the agent pipeline one studio.
                </p>
              </div>
              <button type="button" onClick={() => setOpen(true)} className="btn-primary shrink-0">
                New manuscript
              </button>
            </header>

            {showWelcome && (
              <div className="mb-8 rounded-[24px] border border-[rgba(104,103,234,0.22)] bg-[linear-gradient(145deg,rgba(238,237,255,0.9),rgba(255,255,255,0.75))] p-5 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="max-w-xl">
                    <p className="text-[15px] font-semibold text-ink-text">
                      {llm.configured ? "Welcome to Novel OS" : "Connect a writing model first"}
                    </p>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
                      {llm.configured
                        ? "Structure first, prose second, continuity always. Create a manuscript, plan an outline, then draft chapter by chapter."
                        : "Agents need an LLM. Open Settings to pick Quality, Fast, Local (Ollama), or Mature-capable (BYOK)."}
                    </p>
                    <ol className="mt-3 list-decimal space-y-1 pl-4 text-[12.5px] text-ink-muted">
                      <li>Configure your model in Settings</li>
                      <li>Create a manuscript</li>
                      <li>Plan outline → plan chapter → generate draft → Final</li>
                    </ol>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link to="/settings" className="btn-primary inline-flex items-center gap-2">
                      <Icon name="sparkles" className="h-3.5 w-3.5" /> Settings
                    </Link>
                    <button
                      type="button"
                      onClick={openSample}
                      disabled={sampleBusy}
                      className="btn-secondary disabled:opacity-40"
                    >
                      {sampleBusy ? "Opening…" : "Open sample"}
                    </button>
                    <button type="button" onClick={() => setTourOpen(true)} className="btn-ghost">
                      Tour
                    </button>
                    {llm.onboarding_completed === false && (
                      <button type="button" onClick={dismissOnboarding} className="btn-ghost">
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="mb-4 rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/80 px-4 py-3 text-[13px] text-ink-text">
                Failed to load projects: {error}
              </div>
            )}

            {!error && !projects && <SkeletonGrid />}

            {!error && projects && projects.length === 0 && (
              <div className="rounded-[24px] border border-dashed border-[rgba(74,91,133,0.18)] bg-white/50 px-8 py-14 text-center">
                <p className="font-display text-[18px] tracking-[-0.02em] text-ink-text">No manuscripts yet</p>
                <p className="mt-2 text-[13px] text-ink-muted">Start with a title and a genre.</p>
                <button type="button" onClick={() => setOpen(true)} className="btn-primary mt-5">
                  New manuscript
                </button>
                <button
                  type="button"
                  onClick={openSample}
                  disabled={sampleBusy}
                  className="btn-secondary mt-3 disabled:opacity-40"
                >
                  {sampleBusy ? "Opening…" : "Try the sample tour"}
                </button>
              </div>
            )}

            {projects && projects.length > 0 && (
              <motion.div
                variants={grid}
                initial="hidden"
                animate="show"
                className="grid grid-cols-1 gap-4 sm:grid-cols-2"
              >
                {projects.map((p) => (
                  <motion.div key={p.id} variants={card}>
                    <ProjectCard p={p} />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>

      <NewProjectModal open={open} onClose={() => setOpen(false)} />
      <TourModal
        open={tourOpen}
        onClose={() => setTourOpen(false)}
        onOpenSample={openSample}
        sampleBusy={sampleBusy}
        onDismiss={async () => {
          await dismissOnboarding();
          setTourOpen(false);
        }}
      />
    </Scene>
  );
}

const TOUR_STEPS = [
  {
    title: "Connect a model",
    body: "Open Settings and pick Quality, Fast, Local (Ollama), or Mature-capable (BYOK). Agents need a live LLM before drafting feels real.",
  },
  {
    title: "Create or open a manuscript",
    body: "Start blank, or open the Glass Harbor sample it ships with Codex entries, an outline, and a short draft.",
  },
  {
    title: "Run the pipeline",
    body: "Plan outline → plan chapter → draft → edit → validate. Each stage leaves an artifact you can open and revise.",
  },
  {
    title: "Trust continuity",
    body: "Dashboard health and Notes → Continuity show free deterministic checks. The Guardian also reads your Codex as ground truth.",
  },
];

function TourModal({
  open, onClose, onOpenSample, sampleBusy, onDismiss,
}: {
  open: boolean;
  onClose: () => void;
  onOpenSample: () => void;
  sampleBusy: boolean;
  onDismiss: () => void;
}) {
  const [step, setStep] = useState(0);

  // Restart the tour each time it opens, during render so step 1 is what the
  // dialog paints first.
  const [lastOpen, setLastOpen] = useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) setStep(0);
  }

  const current = TOUR_STEPS[step];

  return (
    <Modal open={open} onClose={onClose} title="Studio tour">
      <p className="text-[12px] font-medium text-ink-muted">
        Step {step + 1} of {TOUR_STEPS.length}
      </p>
      <h3 className="mt-2 font-display text-[20px] font-semibold tracking-tight text-ink-text">
        {current.title}
      </h3>
      <p className="mt-2 text-[14px] leading-relaxed text-ink-muted">{current.body}</p>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <button type="button" onClick={onDismiss} className="btn-ghost text-[12.5px]">
          Skip
        </button>
        <div className="flex flex-wrap gap-2">
          {step > 0 && (
            <button type="button" onClick={() => setStep((s) => s - 1)} className="btn-ghost">
              Back
            </button>
          )}
          {step < TOUR_STEPS.length - 1 ? (
            <button type="button" onClick={() => setStep((s) => s + 1)} className="btn-primary">
              Next
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={onOpenSample}
                disabled={sampleBusy}
                className="btn-secondary disabled:opacity-40"
              >
                {sampleBusy ? "Opening…" : "Open sample"}
              </button>
              <button type="button" onClick={onDismiss} className="btn-primary">
                Done
              </button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}

function NewProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [genres, setGenres] = useState<string[]>([]);
  const [otherGenre, setOtherGenre] = useState("");
  const [premise, setPremise] = useState("");
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      const merged = mergeGenres(genres, otherGenre);
      const p = await api.createProject({
        title: title.trim(),
        author: author.trim(),
        genres: merged,
        genre: merged.join(" · "),
        premise: premise.trim(),
      });
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
        <Field label="Author">
          <input
            className={fieldClass}
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Your name"
            autoComplete="name"
          />
        </Field>
        <div className="mb-4">
          <span className="mb-1.5 block text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
            Genres
          </span>
          <GenreChips
            selected={genres}
            onChange={setGenres}
            other={otherGenre}
            onOtherChange={setOtherGenre}
          />
          <p className="mt-1.5 text-[11.5px] text-ink-muted">
            Pick one or more. Hybrids welcome.
          </p>
        </div>
        <div className="mb-4">
          <label htmlFor="manuscript-premise" className="mb-1.5 block text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
            Premise
          </label>
          <textarea
            id="manuscript-premise"
            className={textareaClass}
            value={premise}
            onChange={(e) => setPremise(e.target.value)}
            placeholder="A fogbound port, a compass that won’t point north…"
            rows={2}
          />
          <p className="mt-1.5 text-[11.5px] text-ink-muted">
            Optional. Two to four sentences the Architect can plan from.
          </p>
        </div>
        <div className="sticky bottom-0 -mx-1 mt-4 flex justify-end gap-3 border-t border-[rgba(74,91,133,0.08)] bg-gradient-to-t from-white/95 via-white/90 to-transparent px-1 pb-1 pt-4">
          <button type="button" onClick={onClose} className="btn-ghost">
            Cancel
          </button>
          <button type="submit" disabled={!title.trim() || busy} className="btn-primary disabled:opacity-40">
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {[0, 1].map((i) => (
        <div key={i} className="h-44 animate-pulse rounded-[22px] bg-white/50" />
      ))}
    </div>
  );
}
