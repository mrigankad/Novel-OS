import { api } from "@/lib/api";

export type ImageKind = "cover" | "portrait" | "map" | "image" | "reference";
export const ASPECTS = ["2:3", "3:4", "1:1", "4:3", "3:2", "16:9", "9:16"] as const;

export interface ImageProvider {
  id: "gemini" | "openai" | "runway" | "higgsfield";
  label: string;
  models: string[];
  default_model: string;
  notes: string;
  connected: boolean;
}

export interface GenerateIn {
  prompt: string;
  provider?: string;
  model?: string;
  aspect?: string;
  kind?: ImageKind;
  codex_entry_id?: string | null;
}

interface RunState { status: string; error: string; output: { media_id?: string } }

export const imagesApi = {
  providers: () => api.get<ImageProvider[]>("/settings/image-providers"),
  draftPrompt: (id: string, kind: ImageKind, codex_entry_id?: string | null) =>
    api.post<{ prompt: string; aspect: string }>(`/projects/${id}/images/prompt`, { kind, codex_entry_id }),
  generate: (id: string, body: GenerateIn) =>
    api.post<{ run_id: string | null; status: string; provider: string; media_id?: string }>(`/projects/${id}/images`, body),
  run: (id: string, rid: string) => api.get<RunState>(`/projects/${id}/runs/${rid}`),
};

export const imageKeys = { providers: ["settings", "image-providers"] as const };
