import { api } from "@/lib/api";

export type Reaction = "none" | "love" | "confused" | "bored" | "hooked";

export interface BetaReader {
  id: string;
  round_id: string;
  name: string;
  email: string | null;
  token: string;
  link: string;
  invited_at: string;
  last_seen_at: string | null;
  furthest_chapter: number;
  finished: boolean;
  comments: number;
}

export interface BetaRound {
  id: string;
  name: string;
  chapters: number[];
  status: "open" | "closed";
  created_at: string;
  closes_at: string | null;
  readers: BetaReader[];
}

export interface BetaComment {
  id: string;
  round_id?: string;
  reader_id?: string;
  reader_name: string;
  chapter: number;
  quote: string;
  from_offset: number | null;
  to_offset: number | null;
  body: string;
  reaction: Reaction;
  created_at: string;
  resolved?: boolean;
}

export interface BetaInsights {
  chapters: { number: number; title: string }[];
  readers: number;
  dropoff: { chapter: number; started: number; finished: number }[];
  heat: { chapter: number; comments: number[]; reactions: Record<Exclude<Reaction, "none">, number[]>; total: number[] }[];
  confused: { chapter: number; quote: string; count: number }[];
  reading_time: { chapter: number; avg_seconds: number; readers: number }[];
}

export interface ReaderView {
  book: { title: string; author: string };
  round: { name: string; closes_at: string | null };
  reader: { name: string; furthest_chapter: number; finished: boolean };
  chapters: { number: number; title: string; text: string }[];
  comments: BetaComment[];
  progress: { chapter: number; percent: number; seconds_read: number }[];
}

export interface CommentFilter {
  round_id?: string;
  chapter?: number;
  reader_id?: string;
  reaction?: Reaction;
}

const base = (id: string) => `/projects/${id}/beta`;

export const bk = {
  rounds: (id: string) => ["p", id, "beta", "rounds"] as const,
  comments: (id: string, f: CommentFilter) => ["p", id, "beta", "comments", f] as const,
  insights: (id: string, round?: string) => ["p", id, "beta", "insights", round ?? "all"] as const,
  reader: (token: string) => ["read", token] as const,
};

function qs(f: object): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const betaApi = {
  rounds: (id: string) => api.get<BetaRound[]>(`${base(id)}/rounds`),
  createRound: (id: string, body: { name: string; chapters: number[] }) => api.post<BetaRound>(`${base(id)}/rounds`, body),
  closeRound: (id: string, rid: string) => api.post<BetaRound>(`${base(id)}/rounds/${rid}/close`),
  addReader: (id: string, rid: string, body: { name: string; email?: string }) =>
    api.post<BetaReader>(`${base(id)}/rounds/${rid}/readers`, body),
  removeReader: (id: string, readerId: string) => api.del(`${base(id)}/readers/${readerId}`),
  comments: (id: string, f: CommentFilter = {}) => api.get<BetaComment[]>(`${base(id)}/comments${qs(f)}`),
  resolve: (id: string, cid: string) => api.post<BetaComment>(`${base(id)}/comments/${cid}/resolve`),
  toMemory: (id: string, cid: string, binding = false) =>
    api.post<{ id: string; kind: string; content: string }>(`${base(id)}/comments/${cid}/to-memory`, { binding }),
  summarize: (id: string, roundId?: string) => api.post<{ run_id: string }>(`${base(id)}/summarize${qs({ round_id: roundId })}`),
  insights: (id: string, roundId?: string) => api.get<BetaInsights>(`${base(id)}/insights${qs({ round_id: roundId })}`),
};

export const readerApi = {
  get: (token: string) => api.get<ReaderView>(`/read/${token}`),
  comment: (token: string, body: { chapter: number; quote: string; from_offset: number | null; to_offset: number | null; body: string; reaction: Reaction }) =>
    api.post<BetaComment>(`/read/${token}/comments`, body),
  progress: (token: string, body: { chapter: number; percent: number; seconds: number }) =>
    api.post<{ finished: boolean }>(`/read/${token}/progress`, body),
};

/** Paragraphs of a chapter with their character offsets into the original text. */
export function paragraphs(text: string): { text: string; start: number }[] {
  const out: { text: string; start: number }[] = [];
  const re = /[^\n]+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m[0].trim()) out.push({ text: m[0], start: m.index });
  }
  return out;
}

export function fmtDuration(s: number): string {
  if (!s) return "–";
  const m = Math.round(s / 60);
  return m < 1 ? `${s}s` : m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}m`;
}
