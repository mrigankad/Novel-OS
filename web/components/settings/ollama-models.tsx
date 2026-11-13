"use client";

import { clsx } from "clsx";
import { Check, Download, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { settingsApi, type Connection } from "@/lib/api/settings";
import { describeProgress, ollamaApi, ollamaKeys, pullModel } from "@/lib/api/ollama";

const SUGGESTIONS: { label: string; model: string }[] = [
  { label: "Best for prose", model: "gemma3:27b" },
  { label: "Fast drafts", model: "qwen3:14b" },
  { label: "Memory recall", model: "nomic-embed-text" },
];

function useSetDefault(conn?: Connection) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (model: string) => settingsApi.update(conn!.id, { default_model: model }),
    onSuccess: (_, model) => { toast(`${model} is now the default`); qc.invalidateQueries({ queryKey: ["settings"] }); },
    onError: (e: Error) => toast(e.message, "error"),
  });
}

/** Installed local models, a pull box with live progress, and delete. */
export function LocalModels({ conn }: { conn?: Connection }) {
  const qc = useQueryClient();
  const toast = useToast();
  const status = useQuery({ queryKey: ollamaKeys.models, queryFn: ollamaApi.models, staleTime: 15_000 });
  const library = useQuery({ queryKey: ollamaKeys.library, queryFn: ollamaApi.library, staleTime: Infinity });
  const setDefault = useSetDefault(conn);
  const remove = useMutation({
    mutationFn: (name: string) => ollamaApi.remove(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const [name, setName] = useState("");
  const [pulling, setPulling] = useState<{ model: string; status: string; percent: number | null } | null>(null);
  const abort = useRef<AbortController | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  async function pull(model: string) {
    const m = model.trim();
    if (!m || pulling) return;
    const ctl = new AbortController();
    abort.current = ctl;
    setPulling({ model: m, status: "starting", percent: null });
    setPullError(null);
    try {
      await pullModel(m, (e) => {
        if (e.event === "progress") setPulling({ model: m, status: describeProgress(e.status, e.percent), percent: e.percent });
        else if (e.event === "done") { toast(`Pulled ${m}`); setName(""); }
        else setPullError(friendlyPullError(m, e.error));
      }, ctl.signal);
    } catch (e) {
      if (!ctl.signal.aborted) setPullError(friendlyPullError(m, (e as Error).message));
      else toast(`Stopped pulling ${m}`);
    } finally {
      setPulling(null);
      abort.current = null;
      qc.invalidateQueries({ queryKey: ollamaKeys.models });
    }
  }

  const data = status.data;
  const current = conn?.default_model ?? "";
  const localLib = (library.data?.models ?? []).filter((m) => !m.cloud);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-[13px] text-body">
        <span className={clsx("h-2 w-2 rounded-full", data?.reachable ? "bg-pass" : "bg-fail")} aria-hidden />
        {status.isLoading ? "Looking for Ollama…" : data?.reachable ? `Ollama ${data.version} · reachable` : "Not running"}
      </div>
      {data && !data.reachable && <p className="text-[13px] text-fail">{data.error}</p>}

      {data?.reachable && (
        <div>
          <p className="label mb-1">Installed · {data.models.length}</p>
          {data.models.length === 0 && <p className="text-[13px] text-muted">No models yet. Pull one below.</p>}
          <ul className="divide-y divide-rule">
            {data.models.map((m) => (
              <li key={m.name} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
                <span className="flex min-w-0 flex-1 items-center gap-2 text-[14px] font-medium text-ink">
                  {m.loaded && <span title="Loaded in memory" className="h-1.5 w-1.5 shrink-0 rounded-full bg-pass" />}
                  <span className="truncate">{m.name}</span>
                </span>
                <span className="text-[13px] text-body">{[m.parameter_size, m.quantization, m.size_human].filter(Boolean).join(" · ")}</span>
                {m.name === current ? (
                  <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-ink">
                    <Check size={14} strokeWidth={1.75} /> Default
                  </span>
                ) : (
                  <Button variant="ghost" size="sm" disabled={!conn || setDefault.isPending} onClick={() => setDefault.mutate(m.name)}>
                    Use as default
                  </Button>
                )}
                <Button variant="ghost" size="sm" aria-label={`Delete ${m.name}`} disabled={remove.isPending}
                  onClick={() => { if (window.confirm(`Delete ${m.name} (${m.size_human}) from this machine?`)) remove.mutate(m.name); }}>
                  <Trash2 size={14} strokeWidth={1.75} />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <p className="label mb-2">Pull a model</p>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void pull(name); }}>
          <Input list="ollama-library" value={name} onChange={(e) => setName(e.target.value)}
            placeholder="e.g. gemma3:27b" disabled={!!pulling || !data?.reachable} aria-label="Model name" />
          <datalist id="ollama-library">
            {localLib.map((m) => <option key={m.name} value={m.name}>{`${m.label} · ${m.size} · ${m.best_for}`}</option>)}
          </datalist>
          <Button type="submit" size="sm" disabled={!name.trim() || !!pulling || !data?.reachable}>
            <Download size={14} strokeWidth={1.75} /> Pull
          </Button>
        </form>
        {pullError && !pulling && (
          <p role="alert" className="mt-2 text-[13px] leading-relaxed text-fail">{pullError}</p>
        )}
        {!pulling && (
          <div className="mt-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s.model} type="button" onClick={() => setName(s.model)}
                className="rounded-full bg-sheet px-3 py-1 text-[13px] text-body transition-colors hover:text-ink">
                {s.label}: <span className="font-medium text-ink">{s.model}</span>
              </button>
            ))}
          </div>
        )}
        {pulling && (
          <div className="mt-3" aria-live="polite">
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-body"><span className="font-medium text-ink">{pulling.model}</span> · {pulling.status}</span>
              <Button variant="ghost" size="sm" onClick={() => abort.current?.abort()}>
                <X size={14} strokeWidth={1.75} /> Cancel
              </Button>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-wash" role="progressbar"
              aria-valuemin={0} aria-valuemax={100} aria-valuenow={pulling.percent ?? undefined}>
              <div className={clsx("h-full rounded-full bg-gall transition-[width] duration-200", pulling.percent === null && "animate-pulse")}
                style={{ width: `${pulling.percent ?? 100}%`, opacity: pulling.percent === null ? 0.35 : 1 }} />
            </div>
          </div>
        )}
        <p className="mt-2 text-[12px] text-muted">Suggestions only; verify sizes on ollama.com/library.</p>
      </div>
    </div>
  );
}

/** Models hosted on ollama.com for the Cloud connection. */
export function CloudModels({ conn }: { conn?: Connection }) {
  const cloud = useQuery({ queryKey: [...ollamaKeys.cloud, conn?.id ?? "none"], queryFn: ollamaApi.cloudModels, enabled: !!conn, staleTime: 60_000 });
  const setDefault = useSetDefault(conn);
  const current = conn?.default_model ?? "";
  if (!conn) return <p className="text-[13px] text-muted">Add your API key and test the connection to see cloud models.</p>;
  if (cloud.isLoading) return <p className="text-[13px] text-muted">Looking for cloud models…</p>;
  if (cloud.data && !cloud.data.ok) return <p className="text-[13px] text-fail">{cloud.data.error}</p>;
  const models = cloud.data?.models ?? [];
  return (
    <div>
      <p className="label mb-1">Cloud models · {models.length}</p>
      <ul className="divide-y divide-rule">
        {models.map((m) => (
          <li key={m.id} className="flex items-center gap-4 py-2.5">
            <span className="min-w-0 flex-1 truncate text-[14px] font-medium text-ink">{m.id}</span>
            {m.parameters && <span className="text-[13px] text-body">{m.parameters}</span>}
            {m.id === current ? (
              <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-ink"><Check size={14} strokeWidth={1.75} /> Default</span>
            ) : (
              <Button variant="ghost" size="sm" disabled={setDefault.isPending} onClick={() => setDefault.mutate(m.id)}>Use as default</Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Ollama's raw errors are registry plumbing; say what it means for the writer. */
function friendlyPullError(model: string, raw: string): string {
  const r = raw.toLowerCase();
  if (r.includes("file does not exist") || r.includes("not found") || r.includes("manifest unknown"))
    return `Ollama couldn't find "${model}". Check the name on ollama.com/library.`;
  if (r.includes("503") || r.includes("connect") || r.includes("timeout") || r.includes("network"))
    return `Ollama couldn't reach its model registry, so "${model}" wasn't downloaded. Check your internet connection or proxy, then try again. (${raw})`;
  if (r.includes("space") || r.includes("disk"))
    return `Not enough disk space to download "${model}".`;
  return `Couldn't pull "${model}": ${raw}`;
}
