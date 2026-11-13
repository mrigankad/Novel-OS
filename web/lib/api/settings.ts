import { api, ApiError } from "@/lib/api";

export interface ProviderInfo {
  id: string;
  label: string;
  description: string;
  fields: ("base_url" | "api_key" | "default_model")[];
  needs_key: boolean;
  default_base_url: string;
  default_model: string;
  help_url: string;
  /** Per-provider field names, e.g. Azure "Endpoint", Bedrock "AWS region". */
  labels?: Partial<Record<"base_url" | "api_key" | "default_model", string>>;
}

export interface Connection {
  id: string;
  provider: string;
  label: string;
  base_url: string;
  default_model: string;
  is_default: boolean;
  has_key: boolean;
  key_last4: string;
  created_at: string | null;
}

export interface DetectedOffer {
  provider: string;
  label: string;
  base_url: string;
  reason: string;
}

export interface ConnectionList {
  connections: Connection[];
  detected: DetectedOffer[];
}

export interface ConnectionInput {
  provider: string;
  label?: string;
  base_url?: string;
  api_key?: string;
  default_model?: string;
}

export interface TestResult {
  ok: boolean;
  latency_ms: number;
  model: string;
  sample?: string;
  tokens_per_s?: number;
  error: string | null;
}

export interface ModelList {
  ok: boolean;
  provider: string;
  endpoint: string;
  models: { id: string; parameters?: string | null }[];
  error: string | null;
  default_model: string;
}

export interface RoleDefault {
  role: string;
  provider: string;
  model: string;
  temperature: number;
}

export interface PlaygroundInput {
  role?: string;
  provider?: string;
  connection_id?: string;
  model?: string;
  prompt?: string;
}

export type PlaygroundEvent =
  | { text: string }
  | { error: string }
  | { done: true; provider: string; model: string; latency_ms: number; tokens_per_s: number };

export const settingsKeys = {
  providers: ["settings", "providers"] as const,
  connections: ["settings", "connections"] as const,
  models: (id: string) => ["settings", "models", id] as const,
  roles: ["settings", "roles"] as const,
};

export const settingsApi = {
  providers: () => api.get<ProviderInfo[]>("/settings/providers"),
  connections: () => api.get<ConnectionList>("/settings/connections"),
  create: (body: ConnectionInput) => api.post<Connection>("/settings/connections", body),
  update: (id: string, body: Partial<ConnectionInput>) => api.patch<Connection>(`/settings/connections/${id}`, body),
  remove: (id: string) => api.del(`/settings/connections/${id}`),
  setDefault: (id: string) => api.post<Connection>(`/settings/connections/${id}/default`),
  test: (id: string) => api.post<TestResult>(`/settings/connections/${id}/test`),
  models: (id: string) => api.get<ModelList>(`/settings/connections/${id}/models`),
  roles: () => api.get<RoleDefault[]>("/settings/roles"),
  saveRoles: (rows: RoleDefault[]) => api.put<RoleDefault[]>("/settings/roles", rows),
};

/** Stream the playground's SSE response, calling onEvent for each event. */
export async function streamPlayground(
  body: PlaygroundInput, onEvent: (e: PlaygroundEvent) => void, signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/settings/playground", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText || "Playground failed");
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
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as PlaygroundEvent);
      }
    }
  }
}
