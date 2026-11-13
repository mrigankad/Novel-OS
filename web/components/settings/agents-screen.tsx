"use client";

import { Compass, Globe, Info, Palette, PenLine, Play, Scissors, Shield, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";
import { Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import {
  settingsApi, settingsKeys, streamPlayground, type Connection, type RoleDefault,
} from "@/lib/api/settings";
import { Sheet } from "./sheet";

const ROLES: { id: string; label: string; icon: LucideIcon; blurb: string }[] = [
  { id: "architect", label: "Architect", icon: Compass, blurb: "Plans structure and beats" },
  { id: "scribe", label: "Scribe", icon: PenLine, blurb: "Drafts the prose" },
  { id: "editor", label: "Editor", icon: Scissors, blurb: "Tightens and revises" },
  { id: "guardian", label: "Guardian", icon: Shield, blurb: "Checks continuity" },
  { id: "curator", label: "Curator", icon: Palette, blurb: "Keeps the voice" },
  { id: "researcher", label: "Researcher", icon: Globe, blurb: "Finds and cites facts" },
];

export function AgentsScreen() {
  const roles = useQuery({ queryKey: settingsKeys.roles, queryFn: settingsApi.roles });
  const conns = useQuery({ queryKey: settingsKeys.connections, queryFn: settingsApi.connections });
  const [trying, setTrying] = useState<RoleDefault | null>(null);
  const list = conns.data?.connections ?? [];
  const fallback = list.find((c) => c.is_default);

  return (
    <Page wide>
      <PageHeader eyebrow="Settings" title="Agents and models"
        description="Pick the model each role writes with. Leave a role on the studio default to follow your default connection." />
      <p className="mt-6 inline-flex items-center gap-2 text-[13px] text-body">
        <Info size={14} strokeWidth={1.75} />
        Per-book overrides live in each book&apos;s Agent room. Manage providers in{" "}
        <Link href="/settings/connections" className="font-medium text-gall hover:underline">Connections</Link>.
      </p>

      <div className="mt-8 overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="border-b border-rule">
              <th className="label py-3 pr-4 font-medium">Role</th>
              <th className="label py-3 pr-4 font-medium">Connection</th>
              <th className="label py-3 pr-4 font-medium">Model</th>
              <th className="label py-3 pr-4 font-medium">Temperature</th>
              <th className="py-3" />
            </tr>
          </thead>
          <tbody>
            {roles.isLoading || conns.isLoading
              ? ROLES.map((r) => (
                <tr key={r.id}><td colSpan={5} className="py-3"><Skeleton className="h-10" /></td></tr>
              ))
              : ROLES.map((r) => {
                const row = roles.data?.find((x) => x.role === r.id) ?? { role: r.id, provider: "", model: "", temperature: 0.7 };
                return <RoleRow key={r.id} meta={r} row={row} connections={list} fallback={fallback}
                  onTry={setTrying} />;
              })}
          </tbody>
        </table>
      </div>

      <TryDrawer row={trying} onClose={() => setTrying(null)} />
    </Page>
  );
}

function RoleRow({ meta, row, connections, fallback, onTry }: {
  meta: (typeof ROLES)[number]; row: RoleDefault; connections: Connection[]; fallback?: Connection;
  onTry: (r: RoleDefault) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [temp, setTemp] = useState(row.temperature);
  const conn = connections.find((c) => c.provider === row.provider) ?? (row.provider ? undefined : fallback);
  const models = useQuery({
    queryKey: settingsKeys.models(conn?.id ?? "none"),
    queryFn: () => settingsApi.models(conn!.id),
    enabled: !!conn,
    staleTime: 60_000,
  });
  const save = useMutation({
    mutationFn: (next: RoleDefault) => settingsApi.saveRoles([next]),
    onSuccess: (data) => qc.setQueryData(settingsKeys.roles, data),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const Icon = meta.icon;
  const modelIds = (models.data?.models ?? []).map((m) => m.id);
  const effectiveModel = row.model || (row.provider ? conn?.default_model : fallback?.default_model) || "";
  if (effectiveModel && !modelIds.includes(effectiveModel)) modelIds.unshift(effectiveModel);

  return (
    <tr className="border-b border-rule align-middle">
      <td className="py-4 pr-4">
        <div className="flex items-center gap-3">
          <Icon size={18} strokeWidth={1.75} className="text-ink" />
          <div>
            <p className="text-[14px] font-semibold text-ink">{meta.label}</p>
            <p className="text-[12px] text-muted">{meta.blurb}</p>
          </div>
        </div>
      </td>
      <td className="py-4 pr-4">
        <select aria-label={`${meta.label} connection`} className={`${inputClass} h-10`} value={row.provider}
          onChange={(e) => save.mutate({ ...row, provider: e.target.value, model: "" })}>
          <option value="">Studio default{fallback ? ` (${fallback.label})` : ""}</option>
          {connections.map((c) => <option key={c.id} value={c.provider}>{c.label}</option>)}
        </select>
      </td>
      <td className="py-4 pr-4">
        <select aria-label={`${meta.label} model`} className={`${inputClass} h-10`} value={row.model}
          disabled={!conn} onChange={(e) => save.mutate({ ...row, model: e.target.value })}>
          <option value="">{effectiveModel ? `Connection default (${conn?.default_model || "auto"})` : "Connection default"}</option>
          {modelIds.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        {models.data && !models.data.ok && <p className="mt-1 text-[12px] text-fail">{models.data.error}</p>}
      </td>
      <td className="py-4 pr-4">
        <div className="flex items-center gap-3">
          <input type="range" min={0} max={1.5} step={0.05} value={temp} aria-label={`${meta.label} temperature`}
            className="w-32 accent-[var(--color-ink)]"
            onChange={(e) => setTemp(Number(e.target.value))}
            onPointerUp={() => save.mutate({ ...row, temperature: temp })}
            onKeyUp={() => save.mutate({ ...row, temperature: temp })} />
          <span className="w-9 text-[13px] tabular-nums text-body">{temp.toFixed(2)}</span>
        </div>
      </td>
      <td className="py-4 text-right">
        <Button size="sm" variant="ai" onClick={() => onTry(row)}>
          <Play size={14} strokeWidth={1.75} /> Try it
        </Button>
      </td>
    </tr>
  );
}

function TryDrawer({ row, onClose }: { row: RoleDefault | null; onClose: () => void }) {
  const [text, setText] = useState("");
  const [meta, setMeta] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!row) return;
    const ctrl = new AbortController();
    abort.current = ctrl;
    // Reset the drawer for this role, then stream a sample into it.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setText(""); setMeta(""); setError(""); setBusy(true);
    streamPlayground({ role: row.role, provider: row.provider || undefined, model: row.model || undefined }, (e) => {
      if ("text" in e) setText((t) => t + e.text);
      else if ("error" in e) setError(e.error);
      else setMeta(`${e.provider} · ${e.model || "default model"} · ${Math.round(e.tokens_per_s)} tokens/s`);
    }, ctrl.signal)
      .catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); })
      .finally(() => setBusy(false));
    return () => ctrl.abort();
  }, [row]);

  const label = ROLES.find((r) => r.id === row?.role)?.label ?? "";
  return (
    <Sheet open={!!row} onClose={() => { abort.current?.abort(); onClose(); }} eyebrow="Try it" title={label}>
      {error ? (
        <p className="text-[14px] text-fail">{error}</p>
      ) : (
        <div className="prose-book whitespace-pre-wrap">
          {text || (busy ? <span className="text-[15px] text-muted">Writing…</span> : null)}
        </div>
      )}
      {meta && <p className="mt-6 text-[12px] text-muted">{meta}</p>}
    </Sheet>
  );
}
