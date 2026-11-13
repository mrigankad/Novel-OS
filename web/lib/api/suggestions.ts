import { api } from "@/lib/api";
import type { Chapter } from "@/lib/api/book";

export type SuggestionKind = "tighten" | "clarity" | "voice" | "continuity" | "grammar";

export interface Suggestion {
  id: string;
  chapter: number;
  run_id: string | null;
  quote: string;
  replacement: string;
  reason: string;
  kind: SuggestionKind | string;
  status: "open" | "accepted" | "dismissed";
  created_at: string;
}

export interface SuggestRun {
  id: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  error?: string;
  output?: { suggestions?: number };
}

const base = (id: string, n: number) => `/projects/${id}/chapters/${n}/suggestions`;

export const sk = {
  list: (id: string, n: number) => ["p", id, "chapter", n, "suggestions"] as const,
  run: (id: string, rid: string) => ["p", id, "run", "suggest", rid] as const,
};

export const suggestionsApi = {
  list: (id: string, n: number) => api.get<Suggestion[]>(base(id, n)),
  start: (id: string, n: number, focus = "") => api.post<{ run_id: string }>(base(id, n), { focus }),
  accept: (id: string, n: number, sid: string) => api.post<Chapter>(`${base(id, n)}/${sid}/accept`),
  dismiss: (id: string, n: number, sid: string) => api.post<Suggestion>(`${base(id, n)}/${sid}/dismiss`),
  acceptAll: (id: string, n: number) => api.post<Chapter>(`${base(id, n)}/accept-all`),
  run: (id: string, rid: string) => api.get<SuggestRun>(`/projects/${id}/runs/${rid}`),
};
