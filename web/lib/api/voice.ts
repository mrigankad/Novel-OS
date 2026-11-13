import { api } from "@/lib/api";

export type Lift = "pure_me" | "me_plus_lift" | "experiment";

export interface VoiceSample {
  id: string;
  title: string;
  word_count: number;
  source: string;
  created_at: string;
  excerpt: string;
}

export interface SignatureMove {
  example: string;
  note: string;
  verbatim?: boolean;
}

export interface VoiceProfile {
  exists: boolean;
  traits: Record<string, unknown>;
  signature_moves: SignatureMove[];
  never: string[];
  lift: Lift;
  style_guide: string;
  words_analyzed: number;
  sample_count: number;
  sample_words: number;
  trait_rows: TraitRow[];
  updated_at: string | null;
}

export interface TraitRow {
  key: string;
  label: string;
  you: number;
  draft: number;
  you_label: string;
  draft_label: string;
  gap: number;
  large: boolean;
}

export interface VoiceMatch {
  chapter: number;
  title: string;
  score: number;
  traits: TraitRow[];
  gaps: string[];
}

export interface ChapterScore {
  chapter: number;
  title: string;
  score: number;
}

const base = (id: string) => `/projects/${id}/voice`;

export const voiceApi = {
  samples: (id: string) => api.get<VoiceSample[]>(`${base(id)}/samples`),
  addText: (id: string, text: string, title = "") => api.post<VoiceSample>(`${base(id)}/samples`, { text, title }),
  addChapter: (id: string, n: number) => api.post<VoiceSample>(`${base(id)}/samples`, { source: `chapter:${n}` }),
  upload: (id: string, file: File, title = "") => {
    const fd = new FormData();
    fd.append("file", file);
    if (title) fd.append("title", title);
    return api.post<VoiceSample>(`${base(id)}/samples`, fd);
  },
  removeSample: (id: string, sampleId: string) => api.del(`${base(id)}/samples/${sampleId}`),
  profile: (id: string) => api.get<VoiceProfile>(`${base(id)}/profile`),
  patchProfile: (id: string, body: Partial<Pick<VoiceProfile, "lift" | "never" | "style_guide">>) =>
    api.patch<VoiceProfile>(`${base(id)}/profile`, body),
  learn: (id: string) => api.post<{ run_id: string; status: string }>(`${base(id)}/learn`),
  match: (id: string, chapter: number) => api.get<VoiceMatch>(`${base(id)}/match?chapter=${chapter}`),
  matchAll: (id: string) => api.get<ChapterScore[]>(`${base(id)}/match/all`),
};

export const voiceKeys = {
  all: (id: string) => ["p", id, "voice"] as const,
  samples: (id: string) => ["p", id, "voice", "samples"] as const,
  profile: (id: string) => ["p", id, "voice", "profile"] as const,
  match: (id: string, n: number) => ["p", id, "voice", "match", n] as const,
  matchAll: (id: string) => ["p", id, "voice", "match", "all"] as const,
};
