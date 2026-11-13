import { api } from "@/lib/api";

export type AudioProviderId = "openai" | "elevenlabs";

export interface AudioProvider {
  id: AudioProviderId;
  label: string;
  default_model: string;
  max_chars: number;
  connected: boolean;
}

export interface Voice { id: string; name: string; hint: string }

export interface CastRow {
  id: string | null;
  codex_entry_id: string | null;
  name: string;
  role: string;
  provider: string;
  voice: string;
  style_instructions: string;
}

export interface Pronunciation { id: string; term: string; say_as: string }

export interface AudioTrack {
  id: string;
  chapter: number;
  provider: string;
  voice: string;
  duration_s: number;
  size: number;
  created_at: string;
  url: string;
}

export interface AudioChapter {
  number: number;
  title: string;
  word_count: number;
  estimated_s: number;
  track: AudioTrack | null;
}

export interface AcxCheck { key: string; label: string; ok: boolean | null; detail: string }
export interface AcxReport {
  files: { chapter: number; track_id: string; checks: AcxCheck[] }[];
  launch_checklist: string[];
}

export interface RenderResult { run_id: string | null; status: string; track?: AudioTrack }
interface RunState { status: string; error: string; output: { track?: AudioTrack } }

const P = (id: string) => `/projects/${id}/audio`;

export const audioApi = {
  providers: () => api.get<AudioProvider[]>("/settings/audio-providers"),
  voices: (provider: string) => api.get<Voice[]>(`/audio/voices?provider=${encodeURIComponent(provider)}`),
  cast: (id: string) => api.get<CastRow[]>(`${P(id)}/cast`),
  saveCast: (id: string, body: Pick<CastRow, "codex_entry_id" | "provider" | "voice" | "style_instructions">) =>
    api.put<CastRow>(`${P(id)}/cast`, body),
  pronunciations: (id: string) => api.get<Pronunciation[]>(`${P(id)}/pronunciations`),
  addPronunciation: (id: string, term: string, say_as: string) =>
    api.post<Pronunciation>(`${P(id)}/pronunciations`, { term, say_as }),
  removePronunciation: (id: string, rid: string) => api.del(`${P(id)}/pronunciations/${rid}`),
  suggest: (id: string) => api.get<string[]>(`${P(id)}/pronunciations/suggest`),
  chapters: (id: string) => api.get<AudioChapter[]>(`${P(id)}/chapters`),
  render: (id: string, n: number, force = false) => api.post<RenderResult>(`${P(id)}/chapters/${n}/render`, { force }),
  run: (id: string, rid: string) => api.get<RunState>(`/projects/${id}/runs/${rid}`),
  acx: (id: string) => api.get<AcxReport>(`${P(id)}/acx`),
  exportUrl: (id: string) => `/api${P(id)}/export`,
  /** Voice preview as an object URL (caller revokes it). */
  sample: async (id: string, body: { provider: string; voice: string; style_instructions: string }) => {
    const res = await fetch(`/api${P(id)}/sample`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail ?? msg; } catch { /* not json */ }
      throw new Error(typeof msg === "string" ? msg : "Preview failed");
    }
    return URL.createObjectURL(await res.blob());
  },
};

export const audioKeys = {
  providers: ["settings", "audio-providers"] as const,
  voices: (provider: string) => ["settings", "audio-voices", provider] as const,
  all: (id: string) => ["p", id, "audio"] as const,
  cast: (id: string) => ["p", id, "audio", "cast"] as const,
  pronunciations: (id: string) => ["p", id, "audio", "pronunciations"] as const,
  chapters: (id: string) => ["p", id, "audio", "chapters"] as const,
  acx: (id: string) => ["p", id, "audio", "acx"] as const,
};

export function formatDuration(s: number): string {
  const total = Math.round(s);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
}
