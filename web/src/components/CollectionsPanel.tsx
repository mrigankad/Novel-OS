import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Collection, type SearchHit } from "../api/client";
import Icon from "./Icon";
import { useToast } from "./toastContext";

/** Saved keyword searches (Scrivener-style collections) over Codex + chapters. */
export default function CollectionsPanel({ projectId }: { projectId: string }) {
  const toast = useToast();
  const [items, setItems] = useState<Collection[]>([]);
  const [name, setName] = useState("");
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.collections(projectId).then(setItems).catch(() => setItems([]));
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true);
    try {
      const list = await api.addCollection(projectId, {
        name: name.trim() || query.trim(),
        query: query.trim(),
      });
      setItems(list);
      setName("");
      setQuery("");
      toast("Collection saved", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function run(col: Collection) {
    setActiveId(col.id);
    try {
      const rows = await api.collectionResults(projectId, col.id);
      setHits(rows);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
      setHits([]);
    }
  }

  async function remove(col: Collection) {
    try {
      await api.deleteCollection(projectId, col.id);
      if (activeId === col.id) {
        setActiveId(null);
        setHits([]);
      }
      load();
      toast("Collection removed", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  function hrefFor(h: SearchHit) {
    if (h.kind === "chapter" && h.chapter != null) {
      return `/projects/${projectId}/chapters/${h.chapter}`;
    }
    if (h.kind === "relationship") return `/projects/${projectId}/chart`;
    return `/projects/${projectId}?codex=${encodeURIComponent(h.id)}`;
  }

  return (
    <div className="rounded-[24px] border border-[rgba(74,91,133,0.12)] bg-white/55 p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-[17px] font-semibold tracking-tight text-ink-text">
            Collections
          </h3>
          <p className="mt-0.5 text-[13px] text-ink-muted">
            Saved searches over Codex and chapters. Semantic collections come later.
          </p>
        </div>
      </div>

      <form onSubmit={create} className="mb-4 flex flex-wrap items-end gap-2">
        <label className="min-w-[8rem] flex-1 text-[12px] font-medium text-ink-muted">
          Name
          <input
            className="mt-1 w-full rounded-full border border-[rgba(96,112,153,0.17)] bg-white/70 px-3 py-2 text-[13.5px] text-ink-text outline-none focus:border-[rgba(104,103,234,0.38)]"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Optional"
          />
        </label>
        <label className="min-w-[12rem] flex-[2] text-[12px] font-medium text-ink-muted">
          Query
          <input
            className="mt-1 w-full rounded-full border border-[rgba(96,112,153,0.17)] bg-white/70 px-3 py-2 text-[13.5px] text-ink-text outline-none focus:border-[rgba(104,103,234,0.38)]"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Lena, harbor, rival"
            required
            minLength={2}
          />
        </label>
        <button type="submit" disabled={busy || query.trim().length < 2} className="btn-secondary disabled:opacity-40">
          {busy ? "Saving…" : "Save"}
        </button>
      </form>

      {items.length === 0 ? (
        <p className="text-[13px] text-paper-muted">No collections yet. Save a keyword search to reopen it later.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((c) => (
            <div key={c.id} className="inline-flex items-center gap-1">
              <button
                type="button"
                onClick={() => run(c)}
                className={`rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                  activeId === c.id
                    ? "bg-[var(--color-violet)] text-white shadow-[0_6px_16px_rgba(104,103,234,0.28)]"
                    : "border border-[rgba(96,112,153,0.16)] bg-white/55 text-ink-muted hover:text-ink"
                }`}
                title={c.query}
              >
                {c.name}
              </button>
              <button
                type="button"
                aria-label={`Remove ${c.name}`}
                onClick={() => remove(c)}
                className="rounded-full px-1.5 py-1 text-[11px] text-ink-muted hover:text-[#c85177]"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {activeId && (
        <ul className="mt-4 max-h-48 space-y-1 overflow-y-auto rounded-2xl border border-[rgba(74,91,133,0.1)] bg-white/70 p-2">
          {hits.length === 0 ? (
            <li className="px-3 py-4 text-center text-[12.5px] text-ink-muted">No matches for this collection.</li>
          ) : (
            hits.map((h) => (
              <li key={`${h.kind}-${h.id}`}>
                <Link
                  to={hrefFor(h)}
                  className="flex items-center gap-2 rounded-xl px-3 py-2 text-[13px] text-ink-text transition-colors hover:bg-[rgba(104,103,234,0.08)]"
                >
                  <Icon name={h.kind === "chapter" ? "scroll-text" : h.kind === "relationship" ? "waypoints" : "book-open"} className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
                  <span className="min-w-0 truncate font-medium">{h.label}</span>
                  <span className="ml-auto shrink-0 capitalize text-[11px] text-paper-muted">{h.kind}</span>
                </Link>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
