import { api } from "@/lib/api";

export type Autonomy = "ask" | "autopilot";
export type AgentRole = "architect" | "scribe" | "editor" | "guardian" | "curator" | "researcher" | "custom" | string;
export type Task = "plan" | "draft" | "revise" | "edit" | "check" | "voice" | "chat";

export interface Agent {
  id: string;
  role: AgentRole;
  name: string;
  brief: string;
  provider: string;
  model: string;
  model_line: string;
  route_provider: string;
  temperature: number;
  use_voice_dna: boolean;
  autonomy: Autonomy;
  enabled: boolean;
  status: "idle" | "writing" | "objection";
  chapters: number[];
}

export interface Run {
  id: string;
  agent_id: string | null;
  task: Task;
  chapter: number | null;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  error: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  output: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export interface MessageAction { label: string; action: string; [k: string]: unknown }

export interface Message {
  id: string;
  thread_id: string;
  sender: string; // author | agent:<id> | system
  recipients: string[];
  body: string;
  intent: "handoff" | "objection" | "proposal" | "question" | "note" | "result" | string;
  actions: MessageAction[];
  run_id: string | null;
  created_at: string;
}

export interface Thread { id: string; title: string; chapter: number | null; kind: string; updated_at: string }

export interface Memory {
  id: string;
  kind: MemoryKind;
  content: string;
  agent_id: string | null;
  chapter: number | null;
  source: string;
  importance: number;
  pinned: boolean;
  recall_count: number;
  last_recalled_at: string | null;
  created_at: string;
}
export type MemoryKind = "fact" | "decision" | "preference" | "episode" | "summary" | "style" | "research";
export const MEMORY_KINDS: MemoryKind[] = ["fact", "decision", "preference", "style", "summary", "research", "episode"];

export interface RoomChapter { number: number; title: string; status: string; assigned_agent_id: string | null }

export interface Stage {
  task: Task; agent_id: string | null; agent_name: string; role: string;
  status: Run["status"] | "idle"; run_id: string | null; error: string;
}
export interface ChapterAgentStatus {
  thread_id: string;
  stages: Stage[];
  objection: Pick<Message, "id" | "body" | "sender" | "actions" | "created_at"> | null;
  context: { memories: number; tokens: number; codex: string[]; run_id: string | null; task: string | null };
}

export interface ResearchItem { id: string; question?: string; title?: string; status?: string }

export const agentKeys = {
  agents: (id: string) => ["p", id, "agent"] as const,
  chapters: (id: string) => ["p", id, "chapter", "room-list"] as const,
  status: (id: string, n: number) => ["p", id, "run", "chapter-status", n] as const,
  thread: (id: string, n: number) => ["p", id, "message", "thread", n] as const,
  messages: (id: string, tid: string) => ["p", id, "message", tid] as const,
  memory: (id: string, filters: Record<string, unknown> = {}) => ["p", id, "memory", filters] as const,
  research: (id: string) => ["p", id, "research", "room"] as const,
  agentRuns: (id: string, aid: string) => ["p", id, "run", "agent", aid] as const,
  activeRuns: (id: string) => ["p", id, "run", "active"] as const,
};

export const CORE_ROLES = ["architect", "scribe", "editor", "guardian", "curator", "researcher"] as const;
export const ALL_ROLES = [...CORE_ROLES, "custom"] as const;

const P = (id: string) => `/projects/${id}`;

export const agentsApi = {
  list: (id: string) => api.get<Agent[]>(`${P(id)}/agents`),
  create: (id: string, body: Partial<Agent> & { name: string }) => api.post<Agent>(`${P(id)}/agents`, body),
  update: (id: string, aid: string, body: Partial<Agent>) => api.patch<Agent>(`${P(id)}/agents/${aid}`, body),
  remove: (id: string, aid: string) => api.del(`${P(id)}/agents/${aid}`),
  setAutonomy: (id: string, autonomy: Autonomy) => api.put<Agent[]>(`${P(id)}/agents-autonomy`, { autonomy }),
  assign: (id: string, n: number, agent_id: string | null) =>
    api.put<{ number: number; assigned_agent_id: string | null }>(`${P(id)}/chapters/${n}/assignee`, { agent_id }),
  run: (id: string, aid: string, task: Task, chapter?: number, instruction = "") =>
    api.post<Run>(`${P(id)}/agents/${aid}/run`, { task, chapter, instruction }),
  chapterTask: (id: string, n: number, task: Task) => api.post<Run>(`${P(id)}/chapters/${n}/tasks/${task}`),
  pipeline: (id: string, n: number) => api.post<Run>(`${P(id)}/chapters/${n}/pipeline`),
  status: (id: string, n: number) => api.get<ChapterAgentStatus>(`${P(id)}/chapters/${n}/agent-status`),
  runs: (id: string, chapter?: number) =>
    api.get<Run[]>(`${P(id)}/runs${chapter != null ? `?chapter=${chapter}` : ""}`),
  agentRuns: (id: string, aid: string, limit = 5) => api.get<Run[]>(`${P(id)}/runs?agent_id=${aid}&limit=${limit}`),
  cancel: (id: string, rid: string) => api.post<Run>(`${P(id)}/runs/${rid}/cancel`),
  chapters: (id: string) => api.get<RoomChapter[]>(`${P(id)}/room/chapters`),

  chapterThread: (id: string, n: number) => api.get<Thread>(`${P(id)}/chapters/${n}/thread`),
  messages: (id: string, tid: string) => api.get<Message[]>(`${P(id)}/threads/${tid}/messages`),
  send: (id: string, tid: string, body: string) =>
    api.post<{ message: Message; runs: string[] }>(`${P(id)}/threads/${tid}/messages`, { body }),
  act: (id: string, tid: string, mid: string, action: string) =>
    api.post<{ ok: boolean; runs: string[]; note: string }>(`${P(id)}/threads/${tid}/messages/${mid}/actions/${action}`),

  memory: (id: string, f: { kind?: string; agent_id?: string; q?: string; chapter?: number } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== "") qs.set(k, String(v)); });
    const s = qs.toString();
    return api.get<Memory[]>(`${P(id)}/memory${s ? `?${s}` : ""}`);
  },
  addMemory: (id: string, body: Partial<Memory> & { content: string }) => api.post<Memory>(`${P(id)}/memory`, body),
  updateMemory: (id: string, mid: string, body: Partial<Memory>) => api.patch<Memory>(`${P(id)}/memory/${mid}`, body),
  removeMemory: (id: string, mid: string) => api.del(`${P(id)}/memory/${mid}`),

  /** Owned by the research area; may not exist yet. Returns [] on 404. */
  research: async (id: string): Promise<ResearchItem[]> => {
    try {
      const r = await api.get<ResearchItem[] | { items?: ResearchItem[] }>(`${P(id)}/research`);
      return Array.isArray(r) ? r : r?.items ?? [];
    } catch {
      return [];
    }
  },
};
