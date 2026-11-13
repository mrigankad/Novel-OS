"use client";

import { Code2, FolderGit2, Globe2, MoreHorizontal, Sparkles, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge, Page, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { settingsApi, settingsKeys, type Connection, type ProviderInfo } from "@/lib/api/settings";
import { AddConnectionSheet } from "./add-connection-sheet";
import { CopyButton } from "./copy-button";
import { OllamaCard } from "./ollama-card";

const CLAUDE_CMD = "claude mcp add novel-os -- python -m server.mcp_server";
const HTTP_CMD = "python -m server.mcp_server --http --port 8765";
const HTTP_URL = "http://127.0.0.1:8765/mcp";

export function ConnectionsScreen() {
  const providers = useQuery({ queryKey: settingsKeys.providers, queryFn: settingsApi.providers, staleTime: Infinity });
  const conns = useQuery({ queryKey: settingsKeys.connections, queryFn: settingsApi.connections });
  const [sheet, setSheet] = useState<ProviderInfo | null>(null);

  const list = conns.data?.connections ?? [];
  const byProvider = new Map(list.map((c) => [c.provider, c]));
  const others = (providers.data ?? []).filter((p) => p.id !== "ollama" && p.id !== "ollama_cloud");

  return (
    <Page wide>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow mb-2">Settings</p>
          <h1 className="font-display text-[48px] font-bold leading-[1.02] tracking-[-0.035em] text-ink">Connections</h1>
          <p className="mt-2 max-w-2xl text-[15px] text-body">
            Choose where the words come from and who can reach your story. Keys stay on this machine.
          </p>
        </div>
        <Badge tone={list.length ? "pass" : "neutral"} dot>{list.length} connected</Badge>
      </header>

      <div className="mt-10 grid gap-12 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <section>
          <h2 className="label mb-4">Models · where the words come from</h2>
          {conns.isLoading ? <Skeleton className="h-80" /> : <OllamaCard connections={list} />}

          {(conns.data?.detected ?? []).length > 0 && (
            <div className="mt-6 flex flex-col gap-2">
              {conns.data!.detected.map((d) => (
                <div key={d.provider} className="flex items-center justify-between gap-3 rounded-[10px] bg-wash px-4 py-3">
                  <p className="text-[13px] text-ink">
                    <Sparkles size={14} strokeWidth={1.75} className="mr-1.5 inline text-gall" />
                    {d.reason}
                  </p>
                  <Button size="sm" variant="ai"
                    onClick={() => setSheet(providers.data?.find((p) => p.id === d.provider) ?? null)}>
                    Add {d.label}
                  </Button>
                </div>
              ))}
            </div>
          )}

          <ul className="mt-6 divide-y divide-rule border-y border-rule">
            {others.map((p) => (
              <ProviderRow key={p.id} provider={p} conn={byProvider.get(p.id)} onAdd={() => setSheet(p)} />
            ))}
          </ul>
        </section>

        <section>
          <h2 className="label mb-4">Agents · who can reach your story</h2>
          <div className="rounded-[16px] bg-ink p-6 text-white">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-[24px] font-bold tracking-[-0.02em]">Claude Code</h3>
              <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-white/60">MCP · stdio</span>
            </div>
            <p className="mt-2 text-[14px] leading-relaxed text-white/75">
              Let Claude Code read your bible, chapters and Codex, write drafts that land in Versions, and run
              continuity, all on this machine.
            </p>
            <div className="mt-5 rounded-[12px] bg-white/10 px-4 py-3 font-sans text-[14px] leading-relaxed text-white">
              {CLAUDE_CMD}
            </div>
            <div className="mt-4">
              <CopyButton text={CLAUDE_CMD} label="Copy command" variant="secondary" />
            </div>
          </div>

          <ul className="mt-6 divide-y divide-rule border-y border-rule">
            <AgentRow icon={Globe2} title="Claude Desktop · Cursor · Codex"
              body={`Run “${HTTP_CMD}”, then add the server at ${HTTP_URL} (Streamable HTTP).`}
              action={<CopyButton text={HTTP_URL} label="Copy URL" variant="ghost" />} />
            <AgentRow icon={FolderGit2} title="Inside this repo"
              body="Hosts that read .mcp.json at the repo root pick up novel-os automatically." />
            <AgentRow icon={Code2} title="REST API"
              body="Everything the studio does is a plain HTTP call under /api. See /docs on the API server." />
          </ul>
        </section>
      </div>

      <AddConnectionSheet provider={sheet} existing={sheet ? byProvider.get(sheet.id) : undefined}
        onClose={() => setSheet(null)} />
    </Page>
  );
}

function ProviderRow({ provider, conn, onAdd }: { provider: ProviderInfo; conn?: Connection; onAdd: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [menu, setMenu] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ["settings"] });
  const makeDefault = useMutation({ mutationFn: () => settingsApi.setDefault(conn!.id), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: () => settingsApi.remove(conn!.id),
    onSuccess: () => { refresh(); toast(`${provider.label} removed`); },
  });
  const test = useMutation({
    mutationFn: () => settingsApi.test(conn!.id),
    onSuccess: (r) => toast(r.ok ? `${provider.label} answered in ${r.latency_ms} ms` : r.error ?? "Failed",
      r.ok ? "success" : "error"),
  });
  return (
    <li className="flex items-center gap-4 py-3.5">
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-ink">
          {provider.label}
          {conn?.is_default && <span className="ml-2 text-[11px] font-semibold text-gall">Default</span>}
        </p>
        <p className="truncate text-[13px] text-body">
          {conn ? `${conn.default_model || "No default model"}${conn.has_key ? ` · key ends ${conn.key_last4 || "····"}` : ""}` : provider.description}
        </p>
      </div>
      {conn ? (
        <div className="relative flex items-center gap-1">
          <Badge tone="pass" dot>Connected</Badge>
          <button type="button" aria-label={`${provider.label} options`} onClick={() => setMenu((m) => !m)}
            className="rounded-[8px] p-1.5 text-body hover:bg-sheet hover:text-ink">
            <MoreHorizontal size={16} strokeWidth={1.75} />
          </button>
          {menu && (
            <div className="absolute right-0 top-9 z-10 flex w-44 flex-col rounded-[10px] bg-paper p-1 shadow-[0_8px_24px_rgba(20,19,26,0.14)] ring-1 ring-rule"
              onMouseLeave={() => setMenu(false)}>
              <MenuItem onClick={() => { setMenu(false); test.mutate(); }}>Test</MenuItem>
              <MenuItem onClick={() => { setMenu(false); onAdd(); }}>Edit</MenuItem>
              {!conn.is_default && (
                <MenuItem onClick={() => { setMenu(false); makeDefault.mutate(); }}>
                  <Star size={14} strokeWidth={1.75} /> Make default
                </MenuItem>
              )}
              <MenuItem danger onClick={() => { setMenu(false); remove.mutate(); }}>
                <Trash2 size={14} strokeWidth={1.75} /> Remove
              </MenuItem>
            </div>
          )}
        </div>
      ) : (
        <Button size="sm" variant="secondary" onClick={onAdd}>Add</Button>
      )}
    </li>
  );
}

function MenuItem({ children, onClick, danger }: { children: React.ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick}
      className={`flex items-center gap-2 rounded-[8px] px-3 py-2 text-left text-[13px] hover:bg-sheet ${danger ? "text-fail" : "text-ink"}`}>
      {children}
    </button>
  );
}

function AgentRow({ icon: Icon, title, body, action }: {
  icon: typeof Globe2; title: string; body: string; action?: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3 py-4">
      <Icon size={18} strokeWidth={1.75} className="mt-0.5 shrink-0 text-body" />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-semibold text-ink">{title}</p>
        <p className="mt-0.5 text-[13px] leading-relaxed text-body">{body}</p>
      </div>
      {action}
    </li>
  );
}
