import { api, type Project } from "@/lib/api";

export type ChapterStatus = "planned" | "drafting" | "drafted" | "revising" | "final";

export interface ChapterRow {
  id: string;
  number: number;
  title: string;
  act: number;
  pov: string;
  status: ChapterStatus | string;
  synopsis: string;
  beats: string[];
  word_count: number;
  target_words: number;
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  updated_at: string;
}

export interface Chapter extends ChapterRow {
  text: string;
  doc: Record<string, unknown>;
}

export type ChapterPatch = Partial<Pick<Chapter,
  "title" | "act" | "pov" | "status" | "synopsis" | "beats" | "target_words" | "text" | "doc">>;

export interface Version {
  id: string;
  chapter_id: string;
  kind: string;
  text: string;
  word_count: number;
  produced_by: string;
  model: string;
  note: string;
  created_at: string;
}

export type CodexKind = "character" | "location" | "item" | "lore" | "faction" | "event" | "theme";

export interface CodexEntry {
  id: string;
  kind: CodexKind | string;
  name: string;
  aliases: string[];
  role: string;
  summary: string;
  facts: Record<string, string>;
  notes: string;
  image_media_id: string | null;
  first_chapter: number | null;
  last_chapter: number | null;
  updated_at: string;
}

export interface CodexLink {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  since_chapter: number | null;
}

export interface PlotThread {
  id: string;
  name: string;
  kind: string;
  status: string;
  priority: number;
  planted_chapter: number | null;
  target_chapter: number | null;
  last_advanced_chapter: number | null;
  notes: string;
}

export type Severity = "critical" | "warning" | "info";

export interface Finding {
  key: string;
  severity: Severity;
  kind: string;
  message: string;
  suggestion: string;
  chapter: number | null;
  entity: string | null;
  fix: { type: "chapter"; chapter: number } | { type: "codex"; id: string } | null;
}

export interface ContinuityReport {
  findings: Finding[];
  counts: Record<Severity, number>;
}

const P = (id: string) => `/projects/${id}`;

export const bookApi = {
  sample: () => api.post<Project>("/projects/sample"),

  chapters: (id: string) => api.get<ChapterRow[]>(`${P(id)}/chapters`),
  chapter: (id: string, n: number) => api.get<Chapter>(`${P(id)}/chapters/${n}`),
  createChapter: (id: string, body: Partial<Chapter>) => api.post<Chapter>(`${P(id)}/chapters`, body),
  updateChapter: (id: string, n: number, body: ChapterPatch) => api.patch<Chapter>(`${P(id)}/chapters/${n}`, body),
  deleteChapter: (id: string, n: number) => api.del(`${P(id)}/chapters/${n}`),
  reorder: (id: string, order: string[]) => api.post<ChapterRow[]>(`${P(id)}/chapters/reorder`, { order }),

  versions: (id: string, n: number) => api.get<Version[]>(`${P(id)}/chapters/${n}/versions`),
  snapshot: (id: string, n: number, note = "") => api.post<Version>(`${P(id)}/chapters/${n}/versions`, { note }),
  restore: (id: string, versionId: string) => api.post<Chapter>(`${P(id)}/versions/${versionId}/restore`),

  codex: (id: string, params: { kind?: string; q?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
    return api.get<CodexEntry[]>(`${P(id)}/codex${qs ? `?${qs}` : ""}`);
  },
  createCodex: (id: string, body: Partial<CodexEntry>) => api.post<CodexEntry>(`${P(id)}/codex`, body),
  updateCodex: (id: string, eid: string, body: Partial<CodexEntry>) => api.patch<CodexEntry>(`${P(id)}/codex/${eid}`, body),
  deleteCodex: (id: string, eid: string) => api.del(`${P(id)}/codex/${eid}`),
  links: (id: string) => api.get<CodexLink[]>(`${P(id)}/codex-links`),
  createLink: (id: string, body: Omit<CodexLink, "id" | "since_chapter"> & { since_chapter?: number | null }) =>
    api.post<CodexLink>(`${P(id)}/codex-links`, body),
  deleteLink: (id: string, linkId: string) => api.del(`${P(id)}/codex-links/${linkId}`),

  threads: (id: string) => api.get<PlotThread[]>(`${P(id)}/plot-threads`),
  createThread: (id: string, body: Partial<PlotThread> & { name: string }) =>
    api.post<PlotThread>(`${P(id)}/plot-threads`, body),
  updateThread: (id: string, tid: string, body: Partial<PlotThread>) =>
    api.patch<PlotThread>(`${P(id)}/plot-threads/${tid}`, body),
  deleteThread: (id: string, tid: string) => api.del(`${P(id)}/plot-threads/${tid}`),

  continuity: (id: string, chapter?: number) =>
    api.get<ContinuityReport>(`${P(id)}/continuity${chapter ? `?chapter=${chapter}` : ""}`),
  exempt: (id: string, f: Finding, reason = "") =>
    api.post(`${P(id)}/continuity/exemptions`, { key: f.key, message: f.message, reason }),
  unexempt: (id: string, key: string) => api.del(`${P(id)}/continuity/exemptions/${encodeURIComponent(key)}`),
};

/** React Query keys. Codex-domain events also cover threads and continuity. */
export const bk = {
  chapters: (id: string) => ["p", id, "chapter", "list"] as const,
  chapter: (id: string, n: number) => ["p", id, "chapter", n] as const,
  versions: (id: string, n: number) => ["p", id, "chapter", n, "versions"] as const,
  codex: (id: string, kind = "") => ["p", id, "codex", "list", kind] as const,
  codexAll: (id: string) => ["p", id, "codex"] as const,
  links: (id: string) => ["p", id, "codex", "links"] as const,
  threads: (id: string) => ["p", id, "codex", "threads"] as const,
  continuity: (id: string, chapter?: number) => ["p", id, "codex", "continuity", chapter ?? "all"] as const,
};

export const ACT_NUMERALS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
export const actLabel = (n: number) => `Act ${ACT_NUMERALS[n] ?? n}`;
