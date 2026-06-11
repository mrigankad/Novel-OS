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
export interface SnapshotMeta {
  id: string; label: string; created_at: string; word_count: number; source: string;
}
export interface SnapshotText extends SnapshotMeta { text: string; }
export interface CommentItem {
  id: string; body: string; quote: string; created_at: string; resolved: boolean;
}
export interface CharacterSummary {
  id: string; full_name: string; role: string;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

async function send<T>(path: string, method: "POST" | "PUT" | "PATCH", body?: unknown): Promise<T> {
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

async function del(path: string): Promise<void> {
  const resp = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw new Error(`${resp.status} ${resp.statusText}`);
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
  characters: (id: string) => get<CharacterSummary[]>(`/api/projects/${id}/characters`),
  addCharacter: (id: string, name: string, role: string) =>
    send<CharacterSummary[]>(`/api/projects/${id}/characters`, "POST", { name, role }),
  runPhase: (id: string, stage: string, params: Record<string, unknown> = {}) =>
    send<JobStatus>(`/api/projects/${id}/run`, "POST", { stage, params }),
  getJob: (jobId: string) => get<JobStatus>(`/api/jobs/${jobId}`),
  exportUrl: (id: string) => `${BASE}/api/projects/${id}/export`,
  // snapshots
  snapshots: (id: string, n: number) =>
    get<SnapshotMeta[]>(`/api/projects/${id}/chapters/${n}/snapshots`),
  createSnapshot: (id: string, n: number, label: string) =>
    send<SnapshotMeta>(`/api/projects/${id}/chapters/${n}/snapshots`, "POST", { label }),
  getSnapshot: (id: string, n: number, sid: string) =>
    get<SnapshotText>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  restoreSnapshot: (id: string, n: number, sid: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}/restore`, "POST"),
  deleteSnapshot: (id: string, n: number, sid: string) =>
    del(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  // comments
  comments: (id: string, n: number) =>
    get<CommentItem[]>(`/api/projects/${id}/chapters/${n}/comments`),
  addComment: (id: string, n: number, body: string, quote: string) =>
    send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments`, "POST", { body, quote }),
  updateComment: (id: string, n: number, cid: string, resolved: boolean) =>
    send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments/${cid}`, "PATCH", { resolved }),
  deleteComment: (id: string, n: number, cid: string) =>
    del(`/api/projects/${id}/chapters/${n}/comments/${cid}`),
};

