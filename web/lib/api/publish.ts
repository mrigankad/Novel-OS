import { api } from "@/lib/api";

// ---- Types -----------------------------------------------------------------

export const MEDIA_KINDS = ["image", "cover", "portrait", "map", "reference"] as const;
export type MediaKind = (typeof MEDIA_KINDS)[number];

export interface Media {
  id: string;
  project_id: string;
  filename: string;
  content_type: string;
  sha256: string;
  size: number;
  width: number;
  height: number;
  kind: MediaKind;
  caption: string;
  tags: string[];
  source: string;
  url: string;
  created_at: string;
  duplicate: boolean;
}

export type CoverFormat = "ebook" | "paperback" | "hardcover" | "audiobook";
export type Paper = "white" | "cream" | "color";

export interface BarcodeBox { x_in: number; y_in: number; w_in: number; h_in: number }

export interface CoverSpec {
  format: CoverFormat;
  trim: string;
  paper: Paper;
  pages: number;
  pages_source: "auto" | "manual";
  words: number;
  trim_w_in: number;
  trim_h_in: number;
  bleed_in: number;
  spine_in: number;
  wrap_w_in: number;
  wrap_h_in: number;
  safe_margin_in: number;
  spine_text_allowed: boolean;
  barcode_box: BarcodeBox | null;
  pixels: { w: number; h: number } | null;
  back_copy_budget?: number;
  template?: string;
}

export interface CoverDesign {
  id: string;
  project_id: string;
  format: CoverFormat;
  trim: string;
  paper: Paper;
  pages: number | null;
  front_media_id: string | null;
  front: { id: string; url: string; width: number; height: number; content_type: string } | null;
  back_copy: string;
  spine_text: string;
  colors: { background?: string; text?: string; [k: string]: string | undefined };
  layout: Record<string, unknown>;
  selected: boolean;
  created_at: string;
}

export interface PreflightCheck { key: string; label: string; status: "pass" | "warn" | "fail"; detail: string }
export interface Preflight { spec: CoverSpec; checks: PreflightCheck[]; ok: boolean }

export interface CoverConcept {
  name: string;
  mood: string;
  palette: string[];
  composition: string;
  typography: string;
  image_prompt: string;
}

export interface BookMetadata {
  id: string;
  project_id: string;
  subtitle: string;
  series: string;
  series_number: number | null;
  description: string;
  keywords: string[];
  bisac: string[];
  isbn_ebook: string;
  isbn_print: string;
  language: string;
  price: Record<string, number | string>;
  comps: string[];
  updated_at: string;
}

export interface ReleaseItem {
  key: string;
  label: string;
  required: boolean;
  done: boolean;
  auto: boolean;
  detail: string;
  file: string;
}

export type ReleaseStatus = "ready" | "blocked" | "submitted" | "live" | "todo";

export interface Release {
  id: string;
  store: string;
  label: string;
  status: ReleaseStatus;
  computed_status: "ready" | "blocked";
  notes: string;
  items: ReleaseItem[];
  files: string[];
  done: number;
  total: number;
}

export interface ReleaseOverview { releases: Release[]; steps_done: number; steps_total: number }

export const MARKETING_KINDS = [
  { kind: "blurb", label: "Blurb" },
  { kind: "taglines", label: "Taglines" },
  { kind: "query_letter", label: "Query letter" },
  { kind: "synopsis_1p", label: "1-page synopsis" },
  { kind: "newsletter", label: "Newsletter" },
  { kind: "a_plus_copy", label: "A+ copy" },
] as const;
export type MarketingKind = (typeof MARKETING_KINDS)[number]["kind"];

export interface MarketingAsset { id: string; kind: MarketingKind; content: string; model: string; created_at: string }

export const COMPILE_FORMATS = [
  { format: "epub", label: "EPUB" },
  { format: "docx", label: "DOCX" },
  { format: "pdf", label: "Print PDF" },
  { format: "html", label: "HTML" },
  { format: "md", label: "Markdown" },
] as const;

export interface Capabilities { pdf: boolean; images: boolean; formats: string[]; words: number }

// ---- Query keys --------------------------------------------------------------

export const publishKeys = {
  all: (id: string) => ["p", id, "publish"] as const,
  media: (id: string) => ["p", id, "publish", "media"] as const,
  covers: (id: string) => ["p", id, "publish", "covers"] as const,
  spec: (id: string, fmt: string, trim: string, paper: string, pages?: number | null) =>
    ["p", id, "publish", "spec", fmt, trim, paper, pages ?? "auto"] as const,
  preflight: (id: string, coverId: string) => ["p", id, "publish", "preflight", coverId] as const,
  concepts: (id: string) => ["p", id, "publish", "concepts"] as const,
  metadata: (id: string) => ["p", id, "publish", "metadata"] as const,
  releases: (id: string) => ["p", id, "publish", "releases"] as const,
  marketing: (id: string) => ["p", id, "publish", "marketing"] as const,
  capabilities: (id: string) => ["p", id, "publish", "capabilities"] as const,
};

// ---- Calls -------------------------------------------------------------------

export const mediaApi = {
  list: (id: string, filter: { kind?: string; tag?: string } = {}) => {
    const q = new URLSearchParams();
    if (filter.kind) q.set("kind", filter.kind);
    if (filter.tag) q.set("tag", filter.tag);
    const s = q.toString();
    return api.get<Media[]>(`/projects/${id}/media${s ? `?${s}` : ""}`);
  },
  upload: (id: string, files: File[], kind: MediaKind = "image") => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return api.post<Media[]>(`/projects/${id}/media?kind=${kind}`, fd);
  },
  importUrl: (id: string, url: string) => api.post<Media>(`/projects/${id}/media/import`, { url }),
  update: (mediaId: string, body: Partial<Pick<Media, "caption" | "tags" | "kind" | "filename">>) =>
    api.patch<Media>(`/media/${mediaId}`, body),
  remove: (mediaId: string) => api.del(`/media/${mediaId}`),
};

export const coverApi = {
  spec: (id: string, fmt: string, trim: string, paper: string, pages?: number | null) =>
    api.get<CoverSpec>(`/projects/${id}/cover/spec?format=${fmt}&trim=${trim}&paper=${paper}${pages ? `&pages=${pages}` : ""}`),
  list: (id: string) => api.get<CoverDesign[]>(`/projects/${id}/covers`),
  create: (id: string, body: Partial<CoverDesign>) => api.post<CoverDesign>(`/projects/${id}/covers`, body),
  update: (id: string, coverId: string, body: Partial<CoverDesign> & { clear_front?: boolean; clear_pages?: boolean }) =>
    api.patch<CoverDesign>(`/projects/${id}/covers/${coverId}`, body),
  select: (id: string, coverId: string) => api.post<CoverDesign>(`/projects/${id}/covers/${coverId}/select`),
  remove: (id: string, coverId: string) => api.del(`/projects/${id}/covers/${coverId}`),
  preflight: (id: string, coverId: string) => api.get<Preflight>(`/projects/${id}/covers/${coverId}/preflight`),
  exportUrl: (id: string, coverId: string, kind: "pdf" | "jpg") => `/api/projects/${id}/covers/${coverId}/export?kind=${kind}`,
  concepts: (id: string) => api.get<CoverConcept[]>(`/projects/${id}/cover/concepts`),
  generateConcepts: (id: string) => api.post<{ run_id: string }>(`/projects/${id}/cover/concepts`),
};

export const publishApi = {
  metadata: (id: string) => api.get<BookMetadata>(`/projects/${id}/metadata`),
  saveMetadata: (id: string, body: Partial<BookMetadata>) => api.put<BookMetadata>(`/projects/${id}/metadata`, body),
  releases: (id: string) => api.get<ReleaseOverview>(`/projects/${id}/releases`),
  updateRelease: (id: string, store: string, body: { status?: string; notes?: string; checklist?: Record<string, boolean> }) =>
    api.patch<Release>(`/projects/${id}/releases/${store}`, body),
  marketing: (id: string) => api.get<MarketingAsset[]>(`/projects/${id}/marketing`),
  generateMarketing: (id: string, kinds: MarketingKind[]) =>
    api.post<{ run_id: string }>(`/projects/${id}/marketing`, { kinds }),
  removeMarketing: (id: string, assetId: string) => api.del(`/projects/${id}/marketing/${assetId}`),
  compileUrl: (id: string, format: string) => `/api/projects/${id}/compile?format=${format}`,
  capabilities: (id: string) => api.get<Capabilities>(`/projects/${id}/publish/capabilities`),
};
