import { useMemo, useState } from "react";
import { api, type ProjectDetail } from "../api/client";
import { useToast } from "./toastContext";

type SessionState = { startedAt: string; baselineWords: number };

function sessionKey(projectId: string) {
  return `novelos-session-${projectId}`;
}

function loadSession(projectId: string, currentWords: number): SessionState {
  try {
    const raw = localStorage.getItem(sessionKey(projectId));
    if (raw) return JSON.parse(raw) as SessionState;
  } catch { /* ignore */ }
  const fresh: SessionState = {
    startedAt: new Date().toISOString(),
    baselineWords: currentWords,
  };
  localStorage.setItem(sessionKey(projectId), JSON.stringify(fresh));
  return fresh;
}

function pct(n: number, d: number) {
  if (d <= 0) return 0;
  return Math.min(100, Math.round((n / d) * 100));
}

function ProgressRing({
  value, label, sub,
}: { value: number; label: string; sub: string }) {
  const r = 28;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.min(100, Math.max(0, value)) / 100) * c;
  return (
    <div className="flex items-center gap-3">
      <svg width="72" height="72" viewBox="0 0 72 72" className="shrink-0 -rotate-90">
        <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(74,91,133,0.12)" strokeWidth="7" />
        <circle
          cx="36" cy="36" r={r} fill="none"
          stroke="var(--color-violet)" strokeWidth="7" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <div className="min-w-0">
        <p className="nums text-[18px] font-semibold tracking-tight text-ink-text">{value}%</p>
        <p className="text-[12.5px] font-medium text-ink-text">{label}</p>
        <p className="nums text-[11.5px] text-ink-muted">{sub}</p>
      </div>
    </div>
  );
}

/** Project + session word targets (PLAN.md P4). */
export default function WritingTargets({
  projectId,
  project,
  wordCount,
  onUpdated,
}: {
  projectId: string;
  project: ProjectDetail;
  wordCount: number;
  onUpdated: (p: ProjectDetail) => void;
}) {
  const toast = useToast();
  const [session, setSession] = useState<SessionState>(() =>
    loadSession(projectId, wordCount),
  );
  const [editing, setEditing] = useState(false);
  const [projectTarget, setProjectTarget] = useState(project.target_word_count ?? 80000);
  const [sessionTarget, setSessionTarget] = useState(project.session_word_target ?? 1000);
  const [busy, setBusy] = useState(false);

  // Both syncs are prop-driven resets, adjusted during render rather than in an
  // effect so the rings never paint one frame of the previous project's numbers.
  const [lastProject, setLastProject] = useState(projectId);
  if (projectId !== lastProject) {
    setLastProject(projectId);
    setSession(loadSession(projectId, wordCount));
  }

  const targets = `${project.target_word_count ?? 80000}/${project.session_word_target ?? 1000}`;
  const [lastTargets, setLastTargets] = useState(targets);
  if (targets !== lastTargets) {
    setLastTargets(targets);
    setProjectTarget(project.target_word_count ?? 80000);
    setSessionTarget(project.session_word_target ?? 1000);
  }

  const sessionWords = Math.max(0, wordCount - session.baselineWords);
  const projectPct = pct(wordCount, project.target_word_count ?? 80000);
  const sessionPct = pct(sessionWords, project.session_word_target ?? 1000);
  const readingMin = useMemo(() => Math.max(1, Math.round(wordCount / 250)), [wordCount]);

  async function saveTargets() {
    setBusy(true);
    try {
      const p = await api.updateProject(projectId, {
        target_word_count: Math.max(0, Math.floor(projectTarget) || 0),
        session_word_target: Math.max(0, Math.floor(sessionTarget) || 0),
      });
      onUpdated(p);
      setEditing(false);
      toast("Targets saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  function resetSession() {
    const fresh: SessionState = {
      startedAt: new Date().toISOString(),
      baselineWords: wordCount,
    };
    localStorage.setItem(sessionKey(projectId), JSON.stringify(fresh));
    setSession(fresh);
    toast("Session reset", "success");
  }

  return (
    <section className="mb-10 rounded-[24px] border border-[rgba(74,91,133,0.12)] bg-white/55 px-5 py-5 backdrop-blur-md">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold tracking-tight text-ink-text">
            Writing targets
          </h2>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">
            Manuscript · session · ~{readingMin} min reading time
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" onClick={resetSession}>
            Reset session
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setEditing((e) => !e)}
          >
            {editing ? "Cancel" : "Edit targets"}
          </button>
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <ProgressRing
          value={projectPct}
          label="Manuscript"
          sub={`${wordCount.toLocaleString()} / ${(project.target_word_count ?? 80000).toLocaleString()} words`}
        />
        <ProgressRing
          value={sessionPct}
          label="This session"
          sub={`${sessionWords.toLocaleString()} / ${(project.session_word_target ?? 1000).toLocaleString()} words`}
        />
      </div>

      {editing && (
        <div className="mt-5 grid gap-3 border-t border-[rgba(74,91,133,0.1)] pt-4 sm:grid-cols-[1fr_1fr_auto]">
          <label className="block text-[12px] font-medium text-ink-muted">
            Project target
            <input
              type="number"
              min={0}
              step={1000}
              value={projectTarget}
              onChange={(e) => setProjectTarget(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-[rgba(96,112,153,0.16)] bg-white/80 px-3 py-2 text-[13px] text-ink-text"
            />
          </label>
          <label className="block text-[12px] font-medium text-ink-muted">
            Session target
            <input
              type="number"
              min={0}
              step={100}
              value={sessionTarget}
              onChange={(e) => setSessionTarget(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-[rgba(96,112,153,0.16)] bg-white/80 px-3 py-2 text-[13px] text-ink-text"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              disabled={busy}
              onClick={() => void saveTargets()}
              className="btn-primary w-full disabled:opacity-40 sm:w-auto"
            >
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
