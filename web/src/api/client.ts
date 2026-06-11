const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface ProjectSummary {
  id: string; title: string; genre: string; chapter_count: number; status: string;
}
export interface ChapterSummary {
  number: number; title: string; status: string; word_count: number; pov: string;
}
export interface ChapterDetail extends ChapterSummary {
  outline: string | null; draft: string | null;
}
export interface ProjectDetail {
  id: string; title: string; genre: string; author: string;
  chapter_count: number; status: string; style: Record<string, string>;
}
export interface ChapterStages {
  number: number; status: string;
  outline: string | null; draft: string | null;
  revised: string | null; final: string | null;
  continuity: Record<string, unknown> | null;
}
export interface FinalResult {
  final: string; word_count: number;
}
export interface JobStatus {
  job_id: string; kind: string;
  status: "running" | "done" | "error"; error: string | null;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

async function send<T>(path: string, method: "POST" | "PUT", body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = j.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  projects: () => get<ProjectSummary[]>("/api/projects"),
  project: (id: string) => get<ProjectDetail>(`/api/projects/${id}`),
  chapters: (id: string) => get<ChapterSummary[]>(`/api/projects/${id}/chapters`),
  chapter: (id: string, n: number) => get<ChapterDetail>(`/api/projects/${id}/chapters/${n}`),
  stages: (id: string, n: number) => get<ChapterStages>(`/api/projects/${id}/chapters/${n}/stages`),
  promoteFinal: (id: string, n: number) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final/promote`, "POST"),
  saveFinal: (id: string, n: number, text: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final`, "PUT", { text }),
  createProject: (body: { title: string; genre: string; author: string }) =>
    send<ProjectSummary>("/api/projects", "POST", body),
  addCharacter: (id: string, name: string, role: string) =>
    send<{ id: string; full_name: string; role: string }[]>(
      `/api/projects/${id}/characters`, "POST", { name, role }),
  runPhase: (id: string, stage: string, params: Record<string, unknown> = {}) =>
    send<JobStatus>(`/api/projects/${id}/run`, "POST", { stage, params }),
  getJob: (jobId: string) => get<JobStatus>(`/api/jobs/${jobId}`),
  exportUrl: (id: string) => `${BASE}/api/projects/${id}/export`,
};

