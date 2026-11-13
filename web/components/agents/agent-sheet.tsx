"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Plus, Square, Trash2, X } from "lucide-react";
import { createElement, useMemo, useState, type ReactNode } from "react";
import { BrandIcon } from "@/components/brand-icon";
import { Sheet } from "@/components/settings/sheet";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Badge, Skeleton } from "@/components/ui/page";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ALL_ROLES, CORE_ROLES, agentKeys, agentsApi, type Agent, type Autonomy, type RoomChapter, type Run,
} from "@/lib/api/agents";
import { settingsApi, settingsKeys } from "@/lib/api/settings";
import { roleIcon } from "./agent-icon";

const ROLE_LABEL: Record<string, string> = {
  architect: "Architect", scribe: "Scribe", editor: "Editor", guardian: "Guardian",
  curator: "Curator", researcher: "Researcher", custom: "Custom",
};
const TASK_LABEL: Record<string, string> = {
  plan: "Plan", draft: "Draft", revise: "Revise", edit: "Edit", check: "Check", voice: "Voice", chat: "Chat",
};
const RUN_TONE = { queued: "neutral", running: "ai", done: "pass", failed: "fail", cancelled: "warn" } as const;

function RoleIcon({ role }: { role: string }) {
  return createElement(roleIcon(role), { className: "h-3.5 w-3.5", strokeWidth: 1.75 });
}

export function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-wash px-2.5 py-1 text-[12px] font-semibold text-gall">
      <RoleIcon role={role} /> {ROLE_LABEL[role] ?? role}
    </span>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={clsx("relative h-5 w-9 shrink-0 rounded-full transition-colors", checked ? "bg-ink" : "bg-rule-strong")}>
      <span className={clsx("absolute top-0.5 h-4 w-4 rounded-full bg-paper shadow transition-[left]",
        checked ? "left-[18px]" : "left-0.5")} />
    </button>
  );
}

function Row({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-[13px] font-semibold text-ink">{title}</p>
        {hint && <p className="text-[12px] text-muted">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

function Label({ children }: { children: ReactNode }) {
  return <p className="mb-1.5 text-[12px] font-semibold text-ink">{children}</p>;
}

export function duration(r: Pick<Run, "created_at" | "finished_at">): string {
  if (!r.finished_at) return "";
  const s = Math.max(0, (new Date(r.finished_at).getTime() - new Date(r.created_at).getTime()) / 1000);
  return s < 60 ? `${s.toFixed(s < 10 ? 1 : 0)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

/** Chapter chips with add / remove. Calls onAdd / onRemove; parent decides whether that hits the API. */
function ChapterChips({ chosen, chapters, onAdd, onRemove, busy }: {
  chosen: number[]; chapters: RoomChapter[]; onAdd: (n: number) => void; onRemove: (n: number) => void; busy?: boolean;
}) {
  const free = chapters.filter((c) => !chosen.includes(c.number));
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chosen.length === 0 && <span className="text-[12px] text-muted">No chapters assigned.</span>}
      {chosen.map((n) => (
        <span key={n} className="inline-flex items-center gap-1 rounded-full bg-sheet py-0.5 pl-2.5 pr-1 text-[12px] font-semibold text-ink">
          Ch {n}
          <button type="button" aria-label={`Unassign chapter ${n}`} disabled={busy} onClick={() => onRemove(n)}
            className="rounded-full p-0.5 text-muted hover:bg-rule hover:text-ink">
            <X className="h-3 w-3" strokeWidth={1.75} />
          </button>
        </span>
      ))}
      {free.length > 0 && (
        <span className="relative inline-flex items-center">
          <Plus className="pointer-events-none absolute left-2 z-10 h-3 w-3 text-body" strokeWidth={1.75} />
          <Select<number> aria-label="Assign a chapter" value={null} disabled={busy} size="sm" placeholder="Add chapter"
            onChange={(v) => onAdd(v)} menuClassName="w-64"
            className="[&>button]:h-6 [&>button]:rounded-full [&>button]:border-dashed [&>button]:pl-6 [&>button]:pr-2 [&>button]:text-[12px] [&>button]:font-semibold [&>button>span]:text-body"
            options={free.map((c) => ({ value: c.number, label: `Chapter ${c.number}${c.title ? ` · ${c.title}` : ""}` }))} />
        </span>
      )}
    </div>
  );
}

type Draft = Pick<Agent, "name" | "brief" | "provider" | "model" | "temperature" | "use_voice_dna" | "autonomy" | "enabled">;
const STUDIO = "__studio";
const ROLE = "__role";

/** Model routing: connection select (with brand icon) + model select filled from that connection. */
function ModelPicker({ agent, draft, set }: { agent?: Agent; draft: Draft; set: (d: Partial<Draft>) => void }) {
  const conns = useQuery({ queryKey: settingsKeys.connections, queryFn: settingsApi.connections });
  const roles = useQuery({ queryKey: settingsKeys.roles, queryFn: settingsApi.roles });
  const list = conns.data?.connections ?? [];
  const studio = list.find((c) => c.is_default);
  const roleDefault = roles.data?.find((r) => r.role === agent?.role && r.provider);
  const conn = draft.provider ? list.find((c) => c.provider === draft.provider) : undefined;
  // An agent pinned to the studio default's provider with no model reads as "studio default".
  const source = !draft.provider ? ROLE : (studio && draft.provider === studio.provider && !draft.model ? STUDIO : conn?.id ?? draft.provider);
  const models = useQuery({
    queryKey: settingsKeys.models(conn?.id ?? "none"),
    queryFn: () => settingsApi.models(conn!.id),
    enabled: !!conn && source !== STUDIO,
    staleTime: 5 * 60_000,
  });
  const modelIds = models.data?.models.map((m) => m.id) ?? [];
  if (draft.model && !modelIds.includes(draft.model)) modelIds.unshift(draft.model);
  const roleIcon = roleDefault?.provider ?? studio?.provider ?? agent?.route_provider;
  const dirty = agent && (agent.provider !== draft.provider || agent.model !== draft.model);

  return (
    <div className="flex flex-col gap-2">
      <Label>Model</Label>
      <Select aria-label="Connection" value={source} className="w-full"
          onChange={(v) => {
            if (v === ROLE) set({ provider: "", model: "" });
            else if (v === STUDIO) set({ provider: studio?.provider ?? "", model: "" });
            else set({ provider: list.find((c) => c.id === v)?.provider ?? "", model: "" });
          }}
          options={[
            { value: ROLE, label: `Use role default${roleDefault ? ` (${roleDefault.provider}${roleDefault.model ? ` · ${roleDefault.model}` : ""})` : ""}`,
              icon: roleIcon ? <BrandIcon id={roleIcon} size="xs" /> : undefined },
            ...(studio ? [{ value: STUDIO, label: `Use studio default (${studio.label || studio.provider})`, icon: <BrandIcon id={studio.provider} size="xs" /> }] : []),
            ...list.map((c) => ({ value: c.id, label: c.label || c.provider, icon: <BrandIcon id={c.provider} size="xs" /> })),
            ...(draft.provider && !conn ? [{ value: draft.provider, label: `${draft.provider} (not connected)`, icon: <BrandIcon id={draft.provider} size="xs" /> }] : []),
          ]} />
      {source !== ROLE && source !== STUDIO && (
        <Select aria-label="Model" value={draft.model} onChange={(v) => set({ model: v })} className="w-full" disabled={models.isLoading}
          options={[
            { value: "", label: models.isLoading ? "Loading models…" : `Connection default${conn?.default_model ? ` (${conn.default_model})` : ""}` },
            ...modelIds.map((m) => ({ value: m, label: m })),
          ]} />
      )}
      {models.data?.error && <p className="text-[12px] text-warn">{models.data.error}</p>}
      {agent && (
        <p className="text-[12px] text-muted">
          {dirty ? "Save to apply. " : ""}Effective now: <span className="font-semibold text-body">{agent.model_line}</span>
          {source === ROLE && !roleDefault && " (no role default set, so the studio default is used)"}
        </p>
      )}
    </div>
  );
}

function RecentRuns({ projectId, agentId }: { projectId: string; agentId: string }) {
  const qc = useQueryClient();
  const runs = useQuery({
    queryKey: agentKeys.agentRuns(projectId, agentId),
    queryFn: () => agentsApi.agentRuns(projectId, agentId, 5),
  });
  const stop = useMutation({
    mutationFn: (rid: string) => agentsApi.cancel(projectId, rid),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["p", projectId, "run"] }),
  });
  if (runs.isLoading) return <Skeleton className="h-24" />;
  if (!runs.data?.length) return <p className="text-[13px] text-body">No runs yet.</p>;
  return (
    <ul className="flex flex-col divide-y divide-rule">
      {runs.data.map((r) => (
        <li key={r.id} className="flex items-start justify-between gap-3 py-2.5">
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-ink">
              {TASK_LABEL[r.task] ?? r.task}{r.chapter != null && <span className="font-normal text-body"> · Ch {r.chapter}</span>}
            </p>
            <p className="truncate text-[12px] text-muted" title={r.error || undefined}>
              {[r.model || r.provider, `${r.tokens_in.toLocaleString()} in · ${r.tokens_out.toLocaleString()} out`, duration(r)]
                .filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {(r.status === "running" || r.status === "queued") && (
              <Button size="sm" variant="ghost" className="h-6 px-2 text-[12px]" disabled={stop.isPending}
                onClick={() => stop.mutate(r.id)}>
                <Square className="h-3 w-3" strokeWidth={1.75} /> Stop
              </Button>
            )}
            <Badge tone={RUN_TONE[r.status]}>{r.status}</Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}

type SheetProps = {
  projectId: string; agent?: Agent; cast: Agent[]; chapters: RoomChapter[]; open: boolean; onClose: () => void;
};

/** Edit an agent (agent set) or create one (agent undefined). Remounts per agent so the form starts fresh. */
export function AgentSheet(props: SheetProps) {
  if (!props.open) return null;
  return <AgentSheetBody key={props.agent?.id ?? "new"} {...props} />;
}

function AgentSheetBody({ projectId, agent, cast, chapters, open, onClose }: SheetProps) {
  const qc = useQueryClient();
  const toast = useToast();
  const creating = !agent;
  const [draft, setDraft] = useState<Draft>(() => {
    if (!agent) return { name: "", brief: "", provider: "", model: "", temperature: 0.8, use_voice_dna: true, autonomy: "ask", enabled: true };
    const { name, brief, provider, model, temperature, use_voice_dna, autonomy, enabled } = agent;
    return { name, brief, provider, model, temperature, use_voice_dna, autonomy, enabled };
  });
  const [role, setRole] = useState<string>("scribe");
  const [newChapters, setNewChapters] = useState<number[]>([]);
  const [confirming, setConfirming] = useState(false);
  const set = (d: Partial<Draft>) => setDraft((x) => ({ ...x, ...d }));

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["p", projectId, "agent"] });
    void qc.invalidateQueries({ queryKey: ["p", projectId, "chapter"] });
    void qc.invalidateQueries({ queryKey: ["p", projectId, "run"] });
  };
  const save = useMutation({
    mutationFn: async () => {
      if (agent) return agentsApi.update(projectId, agent.id, draft);
      const a = await agentsApi.create(projectId, { ...draft, role });
      for (const n of newChapters) await agentsApi.assign(projectId, n, a.id);
      return a;
    },
    onSuccess: (a) => { refresh(); toast(creating ? `${a.name} joined the cast` : "Saved", "success"); if (creating) onClose(); },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const assign = useMutation({
    mutationFn: ({ n, on }: { n: number; on: boolean }) => agentsApi.assign(projectId, n, on ? agent!.id : null),
    onSuccess: refresh,
    onError: (e: Error) => toast(e.message, "error"),
  });
  const remove = useMutation({
    mutationFn: () => agentsApi.remove(projectId, agent!.id),
    onSuccess: () => { refresh(); toast("Agent removed", "success"); onClose(); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const lastOfRole = useMemo(
    () => !!agent && (CORE_ROLES as readonly string[]).includes(agent.role) && cast.filter((a) => a.role === agent.role).length <= 1,
    [agent, cast],
  );
  const dirty = agent ? (Object.keys(draft) as (keyof Draft)[]).some((k) => draft[k] !== agent[k]) : draft.name.trim().length > 0;

  const footer = confirming ? (
    <div className="flex w-full items-center justify-between gap-3">
      <p className="text-[13px] text-ink">Delete <span className="font-semibold">{agent?.name}</span>? Its chapters become unassigned.</p>
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Keep</Button>
        <Button size="sm" variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>Delete</Button>
      </div>
    </div>
  ) : (
    <div className="flex w-full items-center justify-between gap-2">
      {agent ? (
        <Button size="sm" variant="ghost" disabled={lastOfRole} onClick={() => setConfirming(true)}
          title={lastOfRole ? `The only ${ROLE_LABEL[agent.role] ?? agent.role} can't be deleted. Disable it instead.` : undefined}
          className="text-fail hover:text-fail">
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} /> Delete
        </Button>
      ) : <span />}
      <div className="flex gap-2">
        <Button size="sm" variant="ghost" onClick={onClose}>{agent ? "Close" : "Cancel"}</Button>
        <Button size="sm" disabled={!dirty || save.isPending || !draft.name.trim()} onClick={() => save.mutate()}>
          {agent ? "Save" : "Add to cast"}
        </Button>
      </div>
    </div>
  );

  return (
    <Sheet open={open} onClose={onClose} eyebrow={agent ? "Agent" : "New agent"} title={agent ? agent.name : "Add an agent"} footer={footer}>
      <div className="flex flex-col gap-6">
        {creating ? (
          <div>
            <Label>Role</Label>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Role">
              {ALL_ROLES.map((r) => {
                return (
                  <button key={r} type="button" role="radio" aria-checked={role === r} onClick={() => setRole(r)}
                    className={clsx("inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12px] font-semibold transition-colors",
                      role === r ? "border-ink bg-ink text-white" : "border-rule-strong text-body hover:border-body hover:text-ink")}>
                    <RoleIcon role={r} /> {ROLE_LABEL[r]}
                  </button>
                );
              })}
            </div>
            {role === "custom" && <p className="mt-1.5 text-[12px] text-muted">Custom agents start from the Scribe&apos;s instructions plus your brief.</p>}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <RoleBadge role={agent.role} />
            {agent.status !== "idle" && <Badge tone={agent.status === "writing" ? "ai" : "fail"} dot>{agent.status}</Badge>}
          </div>
        )}

        <Field label="Name">
          <Input value={draft.name} onChange={(e) => set({ name: e.target.value })}
            placeholder={creating ? `${ROLE_LABEL[role]} · Tomas chapters` : undefined} />
        </Field>

        <Field label="Brief" hint="standing instructions">
          <Textarea value={draft.brief} onChange={(e) => set({ brief: e.target.value })} rows={4}
            placeholder="Write Iris's chapters. Never use semicolons." />
        </Field>

        <ModelPicker agent={agent} draft={draft} set={set} />

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <Label>Temperature</Label>
            <span className="text-[12px] font-semibold tabular-nums text-ink">{draft.temperature.toFixed(2)}</span>
          </div>
          <input type="range" min={0} max={1.5} step={0.05} value={draft.temperature} aria-label="Temperature"
            onChange={(e) => set({ temperature: Number(e.target.value) })} className="w-full accent-ink" />
          <div className="flex justify-between text-[11px] text-muted"><span>Precise</span><span>Adventurous</span></div>
        </div>

        <div className="flex flex-col gap-4">
          <Row title="Write in my voice" hint="Use your Voice DNA when writing">
            <Switch label="Write in my voice (Voice DNA)" checked={draft.use_voice_dna} onChange={(v) => set({ use_voice_dna: v })} />
          </Row>
          <Row title="Enabled" hint="Disabled agents sit out of the room and the pipeline">
            <Switch label="Enabled" checked={draft.enabled} onChange={(v) => set({ enabled: v })} />
          </Row>
          <div>
            <Label>Autonomy</Label>
            <div className="inline-flex rounded-[10px] bg-sheet p-0.5" role="radiogroup" aria-label="Autonomy">
              {([["ask", "Ask before acting"], ["autopilot", "Autopilot"]] as [Autonomy, string][]).map(([v, l]) => (
                <button key={v} type="button" role="radio" aria-checked={draft.autonomy === v} onClick={() => set({ autonomy: v })}
                  className={clsx("h-8 rounded-[8px] px-3 text-[12px] font-semibold transition-colors",
                    draft.autonomy === v ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.08)]" : "text-body hover:text-ink")}>
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <Label>Assigned chapters</Label>
          {agent ? (
            <ChapterChips chosen={agent.chapters} chapters={chapters} busy={assign.isPending}
              onAdd={(n) => assign.mutate({ n, on: true })} onRemove={(n) => assign.mutate({ n, on: false })} />
          ) : (
            <ChapterChips chosen={newChapters} chapters={chapters}
              onAdd={(n) => setNewChapters((c) => [...c, n].sort((a, b) => a - b))}
              onRemove={(n) => setNewChapters((c) => c.filter((x) => x !== n))} />
          )}
          <p className="mt-1.5 text-[12px] text-muted">Assigned chapters are drafted by this agent when the pipeline runs.</p>
        </div>

        {agent && (
          <div>
            <Label>Recent runs</Label>
            <RecentRuns projectId={projectId} agentId={agent.id} />
          </div>
        )}
      </div>
    </Sheet>
  );
}
