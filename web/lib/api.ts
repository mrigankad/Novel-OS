/**
 * Fetch wrapper for the Novel OS API. Same-origin: Next proxies /api to FastAPI.
 *
 * Each feature keeps its types + calls in lib/api/<feature>.ts and its React
 * Query hooks next to the screen that uses them.
 */

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch { /* not json */ }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T = void>(path: string) => request<T>("DELETE", path),
};

// ---- Projects (shared by every feature) -----------------------------------

export interface Project {
  id: string;
  title: string;
  author: string;
  genre: string;
  premise: string;
  bible: Record<string, unknown>;
  status: string;
  target_words: number;
  word_count: number;
  chapter_count: number;
  cover: { media_id: string | null; background: string; text: string } | null;
  updated_at: string;
}

export const projectsApi = {
  list: () => api.get<Project[]>("/projects"),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (body: Pick<Project, "title"> & Partial<Project>) => api.post<Project>("/projects", body),
  update: (id: string, body: Partial<Project>) => api.patch<Project>(`/projects/${id}`, body),
  remove: (id: string) => api.del(`/projects/${id}`),
};

/** Query keys. Feature modules add their own under ["p", id, ...]. */
export const qk = {
  projects: ["projects"] as const,
  project: (id: string) => ["p", id] as const,
};
