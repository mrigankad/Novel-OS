import { useCallback, useEffect, useState } from "react";
import { api, type CodexEntryType, type CodexProposal } from "../api/client";
import { useToast } from "./toastContext";
import Icon from "./Icon";
import Select from "./Select";

const TYPES: { value: CodexEntryType; label: string }[] = [
  { value: "character", label: "Character" },
  { value: "location", label: "Location" },
  { value: "worldbuilding", label: "World" },
  { value: "item", label: "Item" },
];

/**
 * Review queue for Codex entries found in the manuscript (PLAN.md P2.2).
 *
 * The friction this removes is the category's worst: rival tools make you
 * re-type a cast the draft already contains. Nothing here is ever written
 * without a click - every row is a proposal, and dismissing one is as cheap as
 * accepting it, because a review queue people feel trapped in is a review queue
 * they close.
 *
 * Each row states its own evidence and shows a line of the writer's own prose,
 * so a proposal can be judged without opening the chapter.
 */
export default function CodexProposals({
  projectId,
  onAccepted,
}: {
  projectId: string;
  onAccepted: () => void;
}) {
  const toast = useToast();
  const [proposals, setProposals] = useState<CodexProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [types, setTypes] = useState<Record<string, CodexEntryType>>({});
  const [open, setOpen] = useState(true);

  const load = useCallback(() => {
    api.codexProposals(projectId)
      .then(setProposals)
      .catch(() => setProposals([]))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const visible = proposals.filter((p) => !dismissed.has(p.name));
  if (loading || visible.length === 0) return null;

  async function accept(p: CodexProposal) {
    setBusy(p.name);
    try {
      await api.addCodexEntry(projectId, {
        entry_type: types[p.name] ?? p.entry_type,
        name: p.name,
        summary: p.excerpt,
      });
      // Drop it locally rather than refetching: the writer is mid-triage and a
      // list that reorders under the cursor loses their place.
      setDismissed((d) => new Set(d).add(p.name));
      onAccepted();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section
      aria-label="Codex proposals"
      className="mb-6 rounded-[24px] border border-[rgba(104,103,234,0.22)] bg-[rgba(104,103,234,0.05)] px-5 py-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-1.5 font-display text-[16px] font-semibold tracking-tight text-ink-text">
            <Icon name="sparkles" className="h-4 w-4 text-[var(--color-violet)]" />
            Found in your manuscript
          </h2>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">
            {visible.length} {visible.length === 1 ? "name" : "names"} not in your
            Codex yet. Nothing is saved until you add it.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-ghost px-2.5 py-1 text-[12px]"
            onClick={() => setDismissed(new Set(proposals.map((p) => p.name)))}
          >
            Dismiss all
          </button>
          <button
            type="button"
            aria-expanded={open}
            className="btn-ghost px-2.5 py-1 text-[12px]"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "Hide" : "Show"}
          </button>
        </div>
      </div>

      {open && (
        <ul className="mt-3 space-y-1.5">
          {visible.map((p) => (
            <li
              key={p.name}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-xl border border-[rgba(74,91,133,0.12)] bg-white/70 px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-ink-text">
                  {p.name}
                </p>
                <p className="truncate text-[11.5px] text-ink-muted" title={p.excerpt}>
                  {p.evidence}
                  {p.excerpt ? ` · “${p.excerpt}”` : ""}
                </p>
              </div>

              <Select
                label={`Type for ${p.name}`}
                size="sm"
                value={types[p.name] ?? p.entry_type}
                onChange={(v) =>
                  setTypes((t) => ({ ...t, [p.name]: v as CodexEntryType }))
                }
                options={TYPES}
              />

              <span className="flex shrink-0 gap-1">
                <button
                  type="button"
                  aria-label={`Dismiss ${p.name}`}
                  className="btn-ghost px-2 py-0.5 text-[12px]"
                  onClick={() => setDismissed((d) => new Set(d).add(p.name))}
                >
                  Dismiss
                </button>
                <button
                  type="button"
                  aria-label={`Add ${p.name} to Codex`}
                  disabled={busy === p.name}
                  className="btn-secondary px-2 py-0.5 text-[12px] disabled:opacity-40"
                  onClick={() => void accept(p)}
                >
                  {busy === p.name ? "Adding…" : "Add"}
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
