import { api } from "@/lib/api";

export type ResearchStatus = "queued" | "browsing" | "synthesizing" | "done" | "failed" | "cancelled";

export interface ResearchSource {
  id: string;
  task_id: string;
  url: string;
  domain: string;
  title: string;
  excerpt: string;
  note: string;
  reliability: number;
  filed_to_codex_id: string | null;
  created_at: string;
}

export interface ResearchTask {
  id: string;
  project_id: string;
  question: string;
  chapter: number | null;
  status: ResearchStatus;
  progress: string;
  summary: string;
  source_count: number;
  created_at: string;
  finished_at: string | null;
}

export interface ResearchTaskDetail extends ResearchTask {
  sources: ResearchSource[];
}

export interface ResearchList {
  tasks: ResearchTask[];
  browsers: number;
  sources: number;
  backend: string;
  search_provider: string;
}

export const isRunning = (s: ResearchStatus) => s === "queued" || s === "browsing" || s === "synthesizing";

const base = (id: string) => `/projects/${id}/research`;

export const researchApi = {
  list: (id: string) => api.get<ResearchList>(base(id)),
  get: (id: string, taskId: string) => api.get<ResearchTaskDetail>(`${base(id)}/${taskId}`),
  suggestions: (id: string) => api.get<string[]>(`${base(id)}/suggestions`),
  create: (id: string, body: { question: string; chapter?: number | null }) =>
    api.post<ResearchTaskDetail>(base(id), body),
  cancel: (id: string, taskId: string) => api.post<ResearchTaskDetail>(`${base(id)}/${taskId}/cancel`),
  retry: (id: string, taskId: string) => api.post<ResearchTaskDetail>(`${base(id)}/${taskId}/retry`),
  remove: (id: string, taskId: string) => api.del(`${base(id)}/${taskId}`),
  file: (id: string, sourceId: string, body: { entry_id?: string; name?: string; kind?: string }) =>
    api.post<ResearchSource>(`${base(id)}/sources/${sourceId}/file`, body),
};

/** Query keys under the "research" domain so research.updated events refresh them. */
export const researchKeys = {
  all: (id: string) => ["p", id, "research"] as const,
  list: (id: string) => ["p", id, "research", "list"] as const,
  task: (id: string, taskId: string) => ["p", id, "research", "task", taskId] as const,
  suggestions: (id: string) => ["p", id, "research", "suggestions"] as const,
};
