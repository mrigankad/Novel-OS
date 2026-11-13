import { api, ApiError } from "@/lib/api";

export interface OllamaModel {
  name: string;
  size: number;
  size_human: string;
  family: string;
  parameter_size: string;
  quantization: string;
  modified_at: string | null;
  loaded: boolean;
}

export interface OllamaStatus {
  reachable: boolean;
  base_url: string;
  version: string;
  models: OllamaModel[];
  running: { name: string; size_vram?: number; expires_at?: string; loaded: true }[];
  error: string | null;
}

export interface LibraryModel {
  name: string;
  label: string;
  size: string;
  best_for: string;
  cloud: boolean;
}

export interface CloudModels {
  ok: boolean;
  models: { id: string; parameters?: string | null }[];
  error: string | null;
  default_model: string;
}

export type PullEvent =
  | { event: "progress"; status: string; percent: number | null; completed: number; total: number }
  | { event: "done"; model: string }
  | { event: "error"; error: string };

export const ollamaKeys = {
  models: ["settings", "ollama", "models"] as const,
  library: ["settings", "ollama", "library"] as const,
  cloud: ["settings", "ollama", "cloud"] as const,
};

export const ollamaApi = {
  models: () => api.get<OllamaStatus>("/settings/ollama/models"),
  library: () => api.get<{ note: string; models: LibraryModel[] }>("/settings/ollama/library"),
  cloudModels: () => api.get<CloudModels>("/settings/ollama/cloud-models"),
  remove: (name: string) =>
    api.del(`/settings/ollama/models/${name.split("/").map(encodeURIComponent).join("/")}`),
};

/** POST a pull and parse the SSE reply with a stream reader (EventSource can't POST). */
export async function pullModel(model: string, onEvent: (e: PullEvent) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch("/api/settings/ollama/pull/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not json */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Pull failed");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let name = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) name = line.slice(7).trim();
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent({ event: name, ...JSON.parse(data) } as PullEvent);
    }
  }
}

/** "downloading 41%" style status text for a progress event. */
export function describeProgress(status: string, percent: number | null): string {
  if (status.startsWith("pulling ") && status !== "pulling manifest" && percent !== null) {
    return `downloading ${Math.floor(percent)}%`;
  }
  if (status.startsWith("verifying")) return "verifying";
  return status;
}
