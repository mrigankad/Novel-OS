import { useCallback, useEffect, useState } from "react";
import { api, type ProjectStatistics } from "../api/client";
import Icon from "./Icon";

/** Style Curator surface: reading time, word frequency, echoes (P4). */
export default function ManuscriptStats({ projectId }: { projectId: string }) {
  const [stats, setStats] = useState<ProjectStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(() => {
    api.statistics(projectId)
      .then((s) => {
        setStats(s);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [projectId]);

  // Switching projects puts the panel back into its loading state. Adjusted
  // during render so the effect below only ever writes state asynchronously.
  const [lastProject, setLastProject] = useState(projectId);
  if (projectId !== lastProject) {
    setLastProject(projectId);
    setStats(null);
    setError(null);
    setLoading(true);
  }

  useEffect(() => { fetchStats(); }, [fetchStats]);

  /** Manual refresh from the button; event handlers may set state directly. */
  const load = useCallback(() => {
    setLoading(true);
    fetchStats();
  }, [fetchStats]);

  return (
    <section className="glass-panel mt-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[18px] font-semibold tracking-tight text-ink-text">
            Manuscript statistics
          </h2>
          <p className="mt-1 text-[12.5px] text-ink-muted">
            Style Curator · reading time, frequent words, nearby echoes
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="btn-ghost text-[12px]"
        >
          {loading ? "Scanning…" : "Refresh"}
        </button>
      </div>

      {error && (
        <p className="mt-4 text-[13px] text-[#c85177]">{error}</p>
      )}

      {!error && stats && (
        <>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="Words"
              value={stats.word_count.toLocaleString()}
            />
            <Stat
              label="Reading"
              value={`~${stats.reading_minutes} min`}
            />
            <Stat
              label="Avg sentence"
              value={stats.avg_sentence_length ? `${stats.avg_sentence_length}` : "—"}
            />
            <Stat
              label="With prose"
              value={`${stats.chapters_with_prose}/${stats.chapter_count}`}
            />
          </div>

          {stats.word_count === 0 ? (
            <p className="mt-5 text-[13px] text-ink-muted">
              No draft/revised/final prose yet. Statistics appear once a chapter has text.
            </p>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <h3 className="mb-2.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
                  Top content words
                </h3>
                {stats.top_words.length === 0 ? (
                  <p className="text-[13px] text-ink-muted">Not enough content words yet.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {stats.top_words.slice(0, 12).map((w) => {
                      const max = stats.top_words[0]?.count || 1;
                      const pct = Math.max(8, Math.round((w.count / max) * 100));
                      return (
                        <li key={w.word} className="flex items-center gap-2 text-[13px]">
                          <span className="w-24 truncate font-medium text-ink-text">{w.word}</span>
                          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[rgba(74,91,133,0.1)]">
                            <span
                              className="block h-full rounded-full bg-[var(--color-violet)]/70"
                              style={{ width: `${pct}%` }}
                            />
                          </span>
                          <span className="nums w-8 text-right text-[12px] text-ink-muted">{w.count}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="mb-2.5 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
                  <Icon name="triangle-alert" className="h-3.5 w-3.5" />
                  Echoes
                </h3>
                {stats.echoes.length === 0 ? (
                  <p className="text-[13px] text-ink-muted">
                    No close repeats flagged. Echoes are content words that recur within ~40 words.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {stats.echoes.slice(0, 10).map((e) => (
                      <li
                        key={e.word}
                        className="flex items-center justify-between rounded-xl bg-white/55 px-3 py-2 text-[13px]"
                      >
                        <span className="font-medium text-ink-text">{e.word}</span>
                        <span className="nums text-[12px] text-ink-muted">
                          {e.count}× · {e.close_pairs} close
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white/55 px-3.5 py-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.05em] text-ink-muted">{label}</p>
      <p className="nums mt-1 text-[18px] font-semibold tracking-tight text-ink-text">{value}</p>
    </div>
  );
}
