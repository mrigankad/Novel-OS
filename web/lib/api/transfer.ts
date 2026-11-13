import { api, type Project } from "@/lib/api";

export interface ImportChapter {
  number: number;
  title: string;
  act: number;
  words: number;
}

export interface ImportReport {
  chapters: ImportChapter[];
  words: number;
  detected_by: "headings" | "chapter_lines" | "separators" | "epub_spine" | "single" | string;
  warnings: string[];
  title: string;
}

export interface CodexProposal {
  id: string;
  name: string;
  kind: string;
  summary: string;
  first_chapter: number | null;
  evidence: string;
  status: "open" | "accepted" | "dismissed";
  created_at: string;
}

export interface ExtractRun {
  id: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  error?: string;
  output?: { candidates?: number; proposals?: number };
}

export const IMPORT_ACCEPT = ".docx,.md,.markdown,.txt,.epub";
export const MAX_IMPORT_BYTES = 25 * 1024 * 1024;

const form = (file: File, fields: Record<string, string> = {}) => {
  const f = new FormData();
  f.append("file", file);
  for (const [k, v] of Object.entries(fields)) if (v) f.append(k, v);
  return f;
};

const proposals = (id: string) => `/projects/${id}/codex/proposals`;

export const tk = {
  proposals: (id: string) => ["p", id, "codex", "proposals"] as const,
  run: (id: string, rid: string) => ["p", id, "run", "extract", rid] as const,
};

export const transferApi = {
  preview: (file: File) => api.post<ImportReport>("/projects/import/preview", form(file)),
  importBook: (file: File, meta: { title?: string; author?: string; genre?: string }) =>
    api.post<{ project: Project; report: ImportReport }>("/projects/import", form(file, {
      title: meta.title ?? "", author: meta.author ?? "", genre: meta.genre ?? "",
    })),
  restore: (file: File) => api.post<Project>("/projects/restore", form(file)),
  backupUrl: (id: string) => `/api/projects/${id}/backup`,
  proposals: (id: string) => api.get<CodexProposal[]>(proposals(id)),
  findProposals: (id: string, chapter?: number) => api.post<{ run_id: string }>(proposals(id), { chapter: chapter ?? null }),
  accept: (id: string, pid: string) => api.post<{ proposal: CodexProposal }>(`${proposals(id)}/${pid}/accept`),
  dismiss: (id: string, pid: string) => api.post<CodexProposal>(`${proposals(id)}/${pid}/dismiss`),
  run: (id: string, rid: string) => api.get<ExtractRun>(`/projects/${id}/runs/${rid}`),
};
