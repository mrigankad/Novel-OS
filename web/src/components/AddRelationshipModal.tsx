import { useEffect, useState } from "react";
import { api, type CodexEntry } from "../api/client";
import Modal, { Field, fieldClass } from "./Modal";
import ChoiceGroup from "./ChoiceGroup";
import EntityPicker from "./EntityPicker";
import { useToast } from "./toastContext";
import { BOND_OPTIONS } from "../lib/bonds";


/** Shared Add Relationship form (chart + Codex Connections). */
export default function AddRelationshipModal({
  open,
  onClose,
  characters,
  projectId,
  onAdded,
  prefill,
}: {
  open: boolean;
  onClose: () => void;
  characters: CodexEntry[];
  projectId: string;
  onAdded: () => void;
  prefill?: { source?: string; target?: string } | null;
}) {
  const toast = useToast();
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("ally");
  const [other, setOther] = useState("");
  const [busy, setBusy] = useState(false);

  // Seed the form from the prefill each time the dialog opens. Adjusted during
  // render, not in an effect, so the first paint already shows the right pair.
  const session = open ? `${prefill?.source ?? ""}>${prefill?.target ?? ""}` : null;
  const [lastSession, setLastSession] = useState<string | null>(null);
  if (session !== lastSession) {
    setLastSession(session);
    if (open) {
      const first = prefill?.source ?? characters[0]?.id ?? "";
      const others = characters.filter((c) => c.id !== prefill?.source);
      setSource(first);
      setTarget(
        prefill?.target
        ?? others[0]?.id
        ?? characters.find((c) => c.id !== first)?.id
        ?? "",
      );
      setLabel("ally");
      setOther("");
    }
  }

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const entityOptions = characters.map((c) => ({
    id: c.id,
    name: c.name,
    meta: c.role || undefined,
  }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!source || !target || source === target) return;
    setBusy(true);
    try {
      await api.addRelationship(projectId, {
        source_id: source,
        target_id: target,
        label: label === "other" ? (other.trim() || "unknown") : label,
      });
      toast("Link added", "success");
      onAdded();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Relationship">
      <form onSubmit={submit}>
        <Field label="From">
          <EntityPicker
            label="From"
            value={source}
            onChange={setSource}
            options={entityOptions}
            excludeId={target}
            placeholder="Find who the bond starts with…"
          />
        </Field>
        <Field label="To">
          <EntityPicker
            label="To"
            value={target}
            onChange={setTarget}
            options={entityOptions}
            excludeId={source}
            placeholder="Find who they're linked to…"
          />
        </Field>
        <Field label="Bond">
          <ChoiceGroup
            label="Bond"
            variant="chips"
            size="sm"
            value={label}
            onChange={setLabel}
            options={BOND_OPTIONS}
          />
        </Field>
        {label === "other" && (
          <Field label="Custom label">
            <input
              className={fieldClass}
              value={other}
              onChange={(e) => setOther(e.target.value)}
              placeholder="e.g. childhood friends"
            />
          </Field>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          <button
            type="submit"
            disabled={busy || !source || !target || source === target}
            className="btn-primary disabled:opacity-40"
          >
            {busy ? "Saving…" : "Add"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
