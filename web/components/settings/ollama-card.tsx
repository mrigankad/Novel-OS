"use client";

import { clsx } from "clsx";
import { Cloud, HardDrive, Star } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { settingsApi, type Connection, type TestResult } from "@/lib/api/settings";
import { CloudModels, LocalModels } from "./ollama-models";
import { BrandIcon } from "@/components/brand-icon";

type Mode = "cloud" | "local";
const DEFAULT_BASE: Record<Mode, string> = { cloud: "https://ollama.com", local: "http://localhost:11434" };

/** The featured Ollama card: Local or Cloud, models found, a test prompt. */
export function OllamaCard({ connections }: { connections: Connection[] }) {
  const cloud = connections.find((c) => c.provider === "ollama_cloud");
  const local = connections.find((c) => c.provider === "ollama");
  const [mode, setMode] = useState<Mode>(cloud || !local ? "cloud" : "local");
  const conn = mode === "cloud" ? cloud : local;
  return (
    <section className="rounded-[16px] border-[1.5px] border-gall p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="flex items-center gap-3 font-display text-[24px] font-bold tracking-[-0.02em] text-ink">
              <BrandIcon id="ollama" size="sm" tile /> Ollama
            </h3>
            {conn?.is_default && (
              <span className="rounded-full bg-wash px-2 py-0.5 text-[11px] font-semibold text-gall">Default</span>
            )}
          </div>
          <p className="mt-1 text-[14px] text-body">
            Open models, on this machine or hosted on ollama.com.
          </p>
        </div>
        <div role="tablist" aria-label="Ollama mode" className="inline-flex rounded-[10px] bg-sheet p-1">
          {(["local", "cloud"] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
              className={clsx("inline-flex h-8 items-center gap-1.5 rounded-[8px] px-3 text-[13px] font-semibold transition-colors",
                mode === m ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.08)]" : "text-body hover:text-ink")}>
              {m === "local" ? <HardDrive size={14} strokeWidth={1.75} /> : <Cloud size={14} strokeWidth={1.75} />}
              {m === "local" ? "Local" : "Cloud"}
            </button>
          ))}
        </div>
      </div>
      <OllamaForm key={`${mode}-${conn?.id ?? "new"}`} mode={mode} conn={conn} />
    </section>
  );
}

function OllamaForm({ mode, conn }: { mode: Mode; conn?: Connection }) {
  const qc = useQueryClient();
  const toast = useToast();
  const provider = mode === "cloud" ? "ollama_cloud" : "ollama";
  const [baseUrl, setBaseUrl] = useState(conn?.base_url || DEFAULT_BASE[mode]);
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState<TestResult | null>(null);

  const refresh = () => qc.invalidateQueries({ queryKey: ["settings"] });

  const testIt = useMutation({
    mutationFn: async () => {
      const saved = await settingsApi.create({
        provider, api_key: mode === "cloud" ? apiKey : "",
        base_url: mode === "local" ? baseUrl : "",
        default_model: conn?.default_model ?? "",
      });
      return settingsApi.test(saved.id);
    },
    onSuccess: (r) => { setResult(r); setApiKey(""); refresh(); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const makeDefault = useMutation({ mutationFn: () => settingsApi.setDefault(conn!.id), onSuccess: refresh });

  return (
    <div className="mt-6 flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Base URL">
          <Input value={mode === "cloud" ? DEFAULT_BASE.cloud : baseUrl} disabled={mode === "cloud"}
            onChange={(e) => setBaseUrl(e.target.value)} />
        </Field>
        <Field label="API key" hint="Cloud only">
          <Input type="password" autoComplete="off" disabled={mode === "local"} value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={conn?.has_key ? `Saved · ends ${conn.key_last4 || "····"}` : mode === "cloud" ? "From ollama.com/settings/keys" : "Not needed"} />
        </Field>
      </div>

      {mode === "local" ? <LocalModels conn={conn} /> : <CloudModels conn={conn} />}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4">
        <p className={clsx("text-[13px]", result ? (result.ok ? "text-pass" : "text-fail") : "text-body")}>
          {result
            ? result.ok
              ? `Connected · ${Math.round(result.tokens_per_s ?? 0)} tokens/s on the test prompt`
              : result.error
            : conn ? `Saved · ${conn.default_model || "no default model"}` : "Not connected yet"}
        </p>
        <div className="flex gap-2">
          {conn && !conn.is_default && (
            <Button variant="ghost" size="sm" onClick={() => makeDefault.mutate()}>
              <Star size={14} strokeWidth={1.75} /> Make default
            </Button>
          )}
          <Button size="sm" onClick={() => testIt.mutate()}
            disabled={testIt.isPending || (mode === "cloud" && !apiKey && !conn?.has_key)}>
            {testIt.isPending ? "Testing…" : "Test connection"}
          </Button>
        </div>
      </div>
      {result?.ok && result.sample && (
        <p className="font-prose text-[15px] italic text-body">“{result.sample}…”</p>
      )}
    </div>
  );
}
