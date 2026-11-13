import { useCallback, useEffect, useState } from "react";
import {
  api,
  type ModelCatalog,
  type StudioLlmStatus,
  type StudioPreset,
} from "../api/client";
import Icon from "../components/Icon";
import { useToast } from "../components/toastContext";
import { Field, fieldClass } from "../components/Modal";

/** Per-provider copy for the key / URL fields so writers know what to paste. */
const PROVIDER_FIELDS: Record<string, { key?: string; keyHint?: string; url?: string; urlHint?: string }> = {
  claude_cli: {},
  ollama: { url: "Ollama server", urlHint: "http://localhost:11434" },
  ollama_cloud: { key: "Ollama API key", keyHint: "From ollama.com/settings/keys" },
  anthropic: { key: "Anthropic API key", keyHint: "sk-ant-…" },
  openai: { key: "OpenAI API key", keyHint: "sk-…" },
  openrouter: { key: "OpenRouter API key", keyHint: "sk-or-…" },
  openai_compatible: { key: "API key", keyHint: "Optional", url: "Base URL", urlHint: "https://your-endpoint/v1" },
};

export default function Settings() {
  const toast = useToast();
  const [status, setStatus] = useState<StudioLlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [detecting, setDetecting] = useState(false);

  const provider = status?.provider || "";
  const fields = PROVIDER_FIELDS[provider] ?? { key: "API key", keyHint: "Leave blank to keep the saved key" };

  const detect = useCallback(async (p: string) => {
    if (!p || p === "claude_cli") { setCatalog(null); return; }
    setDetecting(true);
    try {
      setCatalog(await api.studioModels(p, baseUrl.trim() || undefined));
    } catch (e) {
      setCatalog({ ok: false, provider: p, endpoint: "", models: [], error: String(e) });
    } finally {
      setDetecting(false);
    }
  // baseUrl is read at click time on purpose; re-detect is manual after editing it.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.studioLlm().then((s) => {
      setStatus(s);
      setModel(s.model || "");
      void detect(s.provider);
    }).catch((e) => setError(String(e)));
  }, [detect]);

  async function save(body: Parameters<typeof api.updateStudioLlm>[0], message: string) {
    setBusy(true);
    try {
      const next = await api.updateStudioLlm(body);
      setStatus(next);
      setModel(next.model || "");
      setApiKey("");
      toast(message, "success");
      void detect(next.provider);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  const applyPreset = (p: StudioPreset) =>
    save({ preset: p.id, api_key: apiKey.trim() || undefined, base_url: baseUrl.trim() || undefined }, `Switched to ${p.label}`);

  const saveCustom = () =>
    save({
      provider: provider || undefined,
      model: model.trim() || undefined,
      api_key: apiKey.trim() || undefined,
      base_url: baseUrl.trim() || undefined,
    }, "Connection saved");

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 sm:px-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-[44px] font-bold leading-[1.05] tracking-[-0.03em] text-ink-text">
            Connections
          </h1>
          <p className="mt-2 max-w-2xl text-[15px] text-ink-muted">
            Choose where the words come from. Keys stay in your local settings file and never sync.
          </p>
        </div>
        {status && <StatusPill status={status} />}
      </div>

      {error && (
        <div className="mt-6 rounded-lg bg-[color-mix(in_srgb,var(--color-fail)_8%,transparent)] px-4 py-3 text-[13px] text-ink-text">
          Couldn't reach the Novel OS API. Is it running on port 8000? ({error})
        </div>
      )}

      {status && (
        <>
          <SectionLabel>Models · where the words come from</SectionLabel>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {status.presets.map((p) => {
              const active = status.preset === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={busy}
                  onClick={() => applyPreset(p)}
                  aria-pressed={active}
                  className={`rounded-xl border p-4 text-left transition-colors ${
                    active
                      ? "border-violet bg-paper shadow-[0_0_0_1px_var(--color-violet)]"
                      : "border-paper-line bg-paper hover:border-ink-line"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[15px] font-semibold text-ink-text">{p.label}</span>
                    {p.mature_capable && (
                      <span className="rounded-full bg-sheet px-2 py-0.5 text-[11px] font-medium text-ink-muted">
                        Mature-capable
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{p.hint}</p>
                  <p className="mt-2 text-[12px] text-paper-muted">{p.provider} · {p.model}</p>
                </button>
              );
            })}
          </div>

          <SectionLabel>{`${providerLabel(provider)} · model and credentials`}</SectionLabel>
          <div className="rounded-xl border border-paper-line p-6">
            <div className="grid gap-4 sm:grid-cols-2">
              {fields.url && (
                <Field label={fields.url}>
                  <input className={fieldClass} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                         placeholder={fields.urlHint} />
                </Field>
              )}
              {fields.key && (
                <Field label={`${fields.key} (blank keeps the saved one)`}>
                  <input className={fieldClass} type="password" value={apiKey}
                         onChange={(e) => setApiKey(e.target.value)}
                         placeholder={fields.keyHint} autoComplete="off" />
                </Field>
              )}
              <Field label="Model">
                <input className={fieldClass} value={model} onChange={(e) => setModel(e.target.value)}
                       placeholder="Pick below or type an id" />
              </Field>
            </div>

            <ModelPicker
              catalog={catalog}
              detecting={detecting}
              selected={model}
              onPick={setModel}
              onDetect={() => detect(provider)}
              hidden={provider === "claude_cli"}
            />

            <div className="mt-5 flex items-center justify-between border-t border-paper-line pt-4">
              <p className="text-[13px] text-ink-muted">
                {provider === "claude_cli"
                  ? "Using your Claude Code login. No key needed."
                  : "Saving applies to every agent. Per-agent models come next."}
              </p>
              <button type="button" disabled={busy} onClick={saveCustom} className="btn-primary">
                {busy ? "Saving…" : "Save connection"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ModelPicker({
  catalog, detecting, selected, onPick, onDetect, hidden,
}: {
  catalog: ModelCatalog | null; detecting: boolean; selected: string;
  onPick: (id: string) => void; onDetect: () => void; hidden: boolean;
}) {
  if (hidden) return null;
  return (
    <div className="mt-5">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[12px] font-semibold text-ink-text">
          {detecting
            ? "Looking for models…"
            : catalog?.ok
              ? `Found ${catalog.models.length} model${catalog.models.length === 1 ? "" : "s"}`
              : "Available models"}
        </span>
        <button type="button" onClick={onDetect} disabled={detecting} className="btn-ghost text-[12px]">
          <Icon name="search" className="h-3.5 w-3.5" /> Detect
        </button>
      </div>
      {catalog && !catalog.ok && (
        <p className="text-[13px] text-[var(--color-warn)]">{catalog.error}</p>
      )}
      {catalog?.ok && (
        <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto" role="listbox" aria-label="Available models">
          {catalog.models.map((m) => {
            const on = m.id === selected;
            return (
              <button
                key={m.id}
                type="button"
                role="option"
                aria-selected={on}
                onClick={() => onPick(m.id)}
                className={`rounded-md px-2.5 py-1.5 text-[12px] transition-colors ${
                  on ? "bg-violet-soft font-semibold text-violet" : "bg-sheet text-ink-text hover:bg-stone"
                }`}
              >
                {m.id}
                {m.parameters && <span className="ml-1 text-paper-muted">{m.parameters}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: StudioLlmStatus }) {
  const ok = status.configured;
  const color = ok ? "var(--color-pass)" : "var(--color-warn)";
  return (
    <div
      className="flex items-center gap-2 rounded-full px-3.5 py-2 text-[13px] font-semibold"
      style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
      title={status.error ?? undefined}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {ok ? `${providerLabel(status.provider)} · ${status.model || "default model"}` : "Not connected"}
    </div>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <h2 className="mt-10 mb-3 text-[11px] font-medium uppercase tracking-[0.1em] text-paper-muted">{children}</h2>
  );
}

function providerLabel(p: string): string {
  const map: Record<string, string> = {
    ollama: "Ollama (local)", ollama_cloud: "Ollama Cloud", claude_cli: "Claude Code login",
    anthropic: "Anthropic", openai: "OpenAI", openrouter: "OpenRouter", gemini: "Gemini",
    openai_compatible: "Custom endpoint",
  };
  return map[p] ?? (p || "Provider");
}
