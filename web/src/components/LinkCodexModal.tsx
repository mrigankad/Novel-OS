import { useEffect, useMemo, useState } from "react";
import { api, type CodexEntry, type CodexEntryType } from "../api/client";
import Modal, { Field, fieldClass } from "./Modal";
import ChoiceGroup from "./ChoiceGroup";
import { useToast } from "./toastContext";
import type { IconName } from "../icons/registry";

const TYPE_OPTIONS: { value: CodexEntryType; label: string; icon: IconName }[] = [
  { value: "character", label: "Character", icon: "users" },
  { value: "location", label: "Location", icon: "map-pin" },
  { value: "worldbuilding", label: "World", icon: "landmark" },
  { value: "item", label: "Item", icon: "package" },
];

/** Pick an existing Codex entry or create one from the selection. */
export default function LinkCodexModal({
  projectId,
  open,
  mode,
  seedName,
  onClose,
  onLinked,
}: {
  projectId: string;
  open: boolean;
  mode: "link" | "create";
  seedName: string;
  onClose: () => void;
  onLinked: (entry: CodexEntry) => void;
}) {
  const toast = useToast();
  const [entries, setEntries] = useState<CodexEntry[]>([]);
  const [q, setQ] = useState("");
  const [name, setName] = useState(seedName);
  const [entryType, setEntryType] = useState<CodexEntryType>("character");
  const [busy, setBusy] = useState(false);

  // Seed the form when the dialog opens on a new selection. Adjusted during
  // render so the first paint already carries the highlighted name.
  const session = open ? seedName : null;
  const [lastSession, setLastSession] = useState<string | null>(null);
  if (session !== lastSession) {
    setLastSession(session);
    if (open) {
      setName(seedName);
      setQ("");
    }
  }

  useEffect(() => {
    if (!open) return;
    api.codex(projectId).then(setEntries).catch(() => setEntries([]));
  }, [open, projectId]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return entries.slice(0, 12);
    return entries.filter((e) => e.name.toLowerCase().includes(needle)).slice(0, 12);
  }, [entries, q]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const list = await api.addCodexEntry(projectId, {
        entry_type: entryType,
        name: name.trim(),
        role: entryType === "character" ? "supporting" : undefined,
      });
      const created = list.find((x) => x.name.toLowerCase() === name.trim().toLowerCase()) ?? list[0];
      if (!created) throw new Error("Could not create entry");
      toast(`Created ${created.name}`, "success");
      onLinked(created);
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={mode === "link" ? "Link to Codex" : "Create Codex Entry"}>
      {mode === "link" ? (
        <div>
          <Field label="Search">
            <input
              autoFocus
              className={fieldClass}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Find a character, place, or item…"
            />
          </Field>
          <ul className="max-h-56 space-y-1 overflow-y-auto">
            {filtered.length === 0 && (
              <li className="py-6 text-center text-[13px] text-ink-muted">No matching entries.</li>
            )}
            {filtered.map((e) => (
              <li key={`${e.entry_type}-${e.id}`}>
                <button
                  type="button"
                  onClick={() => { onLinked(e); onClose(); }}
                  className="flex w-full items-center justify-between rounded-2xl px-3 py-2.5 text-left transition-colors hover:bg-[rgba(104,103,234,0.08)]"
                >
                  <span className="font-medium text-ink-text">{e.name}</span>
                  <span className="text-[11.5px] capitalize text-ink-muted">{e.entry_type}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex justify-end">
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          </div>
        </div>
      ) : (
        <form onSubmit={create}>
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
            <input autoFocus className={fieldClass} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <div className="mt-6 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
            <button type="submit" disabled={!name.trim() || busy} className="btn-primary disabled:opacity-40">
              {busy ? "Creating…" : "Create & link"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
