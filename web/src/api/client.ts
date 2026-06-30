// Same-origin in dev (Vite proxies /api → backend). Override with VITE_API_BASE if needed.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export interface ProjectSummary {
  id: string; title: string; genre: string; chapter_count: number; status: string;
}
export interface ChapterSummary {
  number: number; title: string; status: string; word_count: number; pov: string;
  pipeline_step: string;
}
export interface ChapterDetail extends ChapterSummary {
  outline: string | null; draft: string | null;
}
export interface ProjectDetail {
  id: string; title: string; genre: string; author: string;
  chapter_count: number; status: string; style: Record<string, string>;
}
export interface ChapterStages {
  number: number; status: string;
  outline: string | null; draft: string | null;
  revised: string | null; final: string | null;
  continuity: Record<string, unknown> | null;
}
export interface FinalResult {
  final: string; word_count: number;
}
export interface UnfinalizeResult {
  number: number; status: string;
  outline: string | null; draft: string | null;
  revised: string | null; final: string | null;
  word_count: number;
}
export interface JobStatus {
  job_id: string; kind: string;
  status: "running" | "done" | "error"; error: string | null;
  project_id?: string;
}
export interface RegeneratePreview {
  text: string;
  source: string;
  original_word_count: number;
  preview_word_count: number;
  generated_at: string | null;
  instructions: string;
  placeholder_count?: number | null;
}
export interface DuplicateMember {
  id: string;
  label: string;
  role?: string | null;
  thread_type?: string | null;
}
export interface DuplicateGroupModel {
  kind: string;
  confidence: number;
  reason: string;
  suggested_keep_id: string;
  members: DuplicateMember[];
}
export interface DuplicatesReport {
  characters: DuplicateGroupModel[];
  plot_threads: DuplicateGroupModel[];
  source: string;
  ai_scan_completed?: boolean;
  scanned_at?: string | null;
}
export interface SnapshotMeta {
  id: string; label: string; created_at: string; word_count: number; source: string;
}
export interface SnapshotText extends SnapshotMeta { text: string; }
export interface CommentItem {
  id: string; body: string; quote: string; created_at: string; resolved: boolean;
}
export interface CharacterSummary {
  id: string; full_name: string; role: string; aliases?: string[];
}
export interface CharacterDetail extends CharacterSummary {
  age: number | null;
  physical_description: string;
  internal_desire: string;
  external_goal: string;
  fear: string;
  weakness: string;
  strength: string;
  secret: string;
  arc_stage: string;
  arc_progress: number;
  current_location: string;
  emotional_state: string;
  notes: string;
  aliases: string[];
  last_appearance_chapter: number;
}
export interface CharacterGeneratePreview {
  character_id: string | null;
  prompt: string;
  hint_name: string;
  hint_role: string;
  updates: Partial<CharacterDetail>;
  generated_at: string | null;
}
export interface BibleDuplicateMember {
  id: string;
  section: string;
  index: number;
  label: string;
}
export interface BibleDuplicateGroup {
  section: string;
  confidence: number;
  reason: string;
  suggested_keep_index: number;
  members: BibleDuplicateMember[];
}
export interface BibleDuplicatesReport {
  groups: BibleDuplicateGroup[];
  source: string;
}
export interface BibleDedupeMerge {
  keep_section: string;
  keep_index: number;
  members: BibleDuplicateMember[];
  text_override?: string;
}
export interface BibleAutoDedupeResult {
  removed: number;
  log: string[];
  keep_text?: string;
}
export interface BibleDedupStatus {
  ai_suggestions_ready: boolean;
  ai_group_count: number;
}
export interface EntityDedupStatus {
  ai_suggestions_ready: boolean;
  ai_group_count: number;
  has_ai_file?: boolean;
  ai_scan_completed?: boolean;
  character_group_count?: number;
  plot_thread_group_count?: number;
}
export interface PlotThreadSummary {
  id: string; name: string; description: string;
  thread_type: string; status: string; priority: number;
  sort_order: number;
  subplots: string[];
}
export interface PlotPanelLocation {
  parent_id: string;
  parent_name: string;
  index: number;
  line: string;
}
export interface PlotPanelIssue {
  issue_id: string;
  kind: string;
  confidence: number;
  reason: string;
  subplot_line: string;
  locations: PlotPanelLocation[];
  thread_id: string | null;
  thread_name: string | null;
  suggested_parent_id: string;
  suggested_parent_name: string;
  suggested_action: string;
}
export interface PlotPanelIssuesReport {
  issues: PlotPanelIssue[];
  source: string;
}
export interface PlotGeneratePreview {
  thread_id: string;
  thread_name: string;
  prompt: string;
  description: string;
  previous_description: string;
  bible_suggestions: string[];
  generated_at: string | null;
}
export interface QuickSlotMeta {
  created_at: string;
  size_bytes: number;
}
export interface QuickBackupMeta {
  current?: QuickSlotMeta | null;
  previous?: QuickSlotMeta | null;
  pre_restore?: QuickSlotMeta | null;
}
export interface NamedBackupMeta {
  id: string;
  label: string;
  created_at: string;
  filename: string;
  size_bytes: number;
}
export interface BackupsReport {
  named: NamedBackupMeta[];
  quick: QuickBackupMeta;
}
export interface BackupActionResult {
  ok: boolean;
  message: string;
  quick?: QuickBackupMeta;
  backup?: NamedBackupMeta;
}

export interface SystemPromptSettings {
  prefix: string;
  agents_dir: string;
}

export interface LlmQueueEntry {
  id: string;
  label: string;
  submitted_at: string;
  chapter?: number | null;
  project_id?: string | null;
  function?: string | null;
}

export interface RunningJobEntry {
  job_id: string;
  kind: string;
  label: string;
  started_at: string;
  project_id?: string | null;
  chapter?: number | null;
  screen?: string;
}

export interface LlmQueueSettings {
  max_concurrent: number;
  active: number;
  queued: number;
  flushed: boolean;
  active_items?: LlmQueueEntry[];
  queued_items?: LlmQueueEntry[];
  running_jobs?: RunningJobEntry[];
}

export interface RestartResult {
  status: string;
  message: string;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

async function getOptional<T>(path: string): Promise<T | null> {
  const resp = await fetch(`${BASE}${path}`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

async function send<T>(path: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = j.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const resp = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw new Error(`${resp.status} ${resp.statusText}`);
}

export const api = {
  projects: () => get<ProjectSummary[]>("/api/projects"),
  project: (id: string) => get<ProjectDetail>(`/api/projects/${id}`),
  chapters: (id: string) => get<ChapterSummary[]>(`/api/projects/${id}/chapters`),
  chapter: (id: string, n: number) => get<ChapterDetail>(`/api/projects/${id}/chapters/${n}`),
  stages: (id: string, n: number) => get<ChapterStages>(`/api/projects/${id}/chapters/${n}/stages`),
  promoteFinal: (id: string, n: number) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final/promote`, "POST"),
  saveFinal: (id: string, n: number, text: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final`, "PUT", { text }),
  unfinalizeChapter: (id: string, n: number) =>
    send<UnfinalizeResult>(`/api/projects/${id}/chapters/${n}/final/unfinalize`, "POST"),
  createProject: (body: { title: string; genre: string; author: string }) =>
    send<ProjectSummary>("/api/projects", "POST", body),
  importStory: (body: {
    chapters_dir: string; title: string; genre: string; author?: string;
    project_id?: string; synthesize?: boolean; no_extract?: boolean;
  }) => send<JobStatus>("/api/import", "POST", body),
  deleteProject: (id: string) => del(`/api/projects/${id}`),
  character: (id: string, charId: string) => get<CharacterDetail>(`/api/projects/${id}/characters/${charId}`),
  updateCharacter: (id: string, charId: string, body: Partial<CharacterDetail>) =>
    send<CharacterDetail>(`/api/projects/${id}/characters/${charId}`, "PATCH", body),
  createChapter: (id: string, body: {
    number: number; title?: string; text?: string; extract?: boolean;
  }) => send<JobStatus | { number: number; word_count: number; changes: string[] }>(
    `/api/projects/${id}/chapters`, "POST", body,
  ),
  updateChapter: (id: string, n: number, body: Record<string, string>) =>
    send<ChapterSummary>(`/api/projects/${id}/chapters/${n}`, "PATCH", body),
  reassignChapter: (id: string, from: number, to: number) =>
    send<{
      action: string; from_number: number; to_number: number;
      chapter: ChapterSummary; swapped_with?: ChapterSummary;
    }>(`/api/projects/${id}/chapters/${from}/reassign`, "POST", { to_number: to }),
  saveDraft: (id: string, n: number, text: string) =>
    send<{ draft: string; word_count: number }>(`/api/projects/${id}/chapters/${n}/draft`, "PUT", { text }),
  saveRevised: (id: string, n: number, text: string) =>
    send<{ revised: string; word_count: number }>(`/api/projects/${id}/chapters/${n}/revised`, "PUT", { text }),
  extractChapter: (id: string, n: number) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/extract`, "POST"),
  mineChapter: (id: string, n: number, kind: "plots" | "characters" | "bible", source = "draft") =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/mine/${kind}?source=${encodeURIComponent(source)}`, "POST"),
  regenerateChapter: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/regenerate`, "POST", body),
  getRegeneratePreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/regenerate/preview`),
  applyRegenerate: (id: string, n: number, body: { text: string; target?: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/regenerate/apply`, "POST", body,
    ),
  discardRegenerate: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/regenerate/preview`),
  expandPlaceholders: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/expand-placeholders`, "POST", body),
  getExpandPreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/expand/preview`),
  applyExpandPreview: (id: string, n: number, body: { text: string; target?: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/expand/apply`, "POST", body,
    ),
  discardExpandPreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/expand/preview`),
  generateOutline: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/generate-outline`, "POST", body),
  getOutlinePreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/generate-outline/preview`),
  applyOutlinePreview: (id: string, n: number, body: { text: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/generate-outline/apply`, "POST", body,
    ),
  discardOutlinePreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/generate-outline/preview`),
  duplicates: (id: string, ai = false) =>
    get<DuplicatesReport>(`/api/projects/${id}/duplicates${ai ? "?ai=true" : ""}`),
  duplicatesStatus: (id: string) =>
    get<EntityDedupStatus>(`/api/projects/${id}/duplicates/status`),
  aiScanDuplicates: (id: string) =>
    send<JobStatus>(`/api/projects/${id}/duplicates/ai-scan`, "POST"),
  autoResolveDuplicates: (id: string) =>
    send<{ merged_characters: number; merged_plot_threads: number; log: string[] }>(
      `/api/projects/${id}/duplicates/auto-resolve`, "POST",
    ),
  mergeDuplicates: (id: string, body: {
    kind: string; keep_id: string; merge_ids: string[]; mode?: string; label_override?: string;
  }) =>
    send<{ kind: string; keep_id: string; merged: string[]; log: string[]; mode?: string; keep_label?: string }>(
      `/api/projects/${id}/duplicates/merge`, "POST", body,
    ),
  nestPlotThreads: (id: string, parentId: string, childIds: string[]) =>
    send<{ kind: string; keep_id: string; merged: string[]; log: string[]; mode?: string }>(
      `/api/projects/${id}/plot-threads/nest`, "POST", { parent_id: parentId, child_ids: childIds },
    ),
  backups: (id: string) => get<BackupsReport>(`/api/projects/${id}/backups`),
  createBackup: (id: string, label: string) =>
    send<NamedBackupMeta>(`/api/projects/${id}/backups`, "POST", { label }),
  restoreBackup: (id: string, backupId: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/${backupId}/restore`, "POST"),
  deleteBackup: (id: string, backupId: string) =>
    del(`/api/projects/${id}/backups/${backupId}`),
  quickSaveBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/quick-save`, "POST"),
  quickRestoreBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/quick-restore`, "POST"),
  undoRestoreBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/undo-restore`, "POST"),
  createPlotThread: (id: string, body: Record<string, unknown>) =>
    send<PlotThreadSummary>(`/api/projects/${id}/plot-threads`, "POST", body),
  updatePlotThread: (id: string, tid: string, body: Record<string, unknown>) =>
    send<PlotThreadSummary>(`/api/projects/${id}/plot-threads/${tid}`, "PATCH", body),
  reorderPlotThreads: (id: string, orderedIds: string[]) =>
    send<PlotThreadSummary[]>(`/api/projects/${id}/plot-threads/reorder`, "PUT", { ordered_ids: orderedIds }),
  storyBible: (id: string) => get<{ data: Record<string, unknown> }>(`/api/projects/${id}/story-bible`),
  updateStoryBible: (id: string, section: string, content: unknown) =>
    send<{ data: Record<string, unknown> }>(`/api/projects/${id}/story-bible`, "PATCH", { section, content }),
  extractBackground: (id: string, text: string, label: string) =>
    send<JobStatus>(`/api/projects/${id}/extract-background`, "POST", { text, label }),
  characters: (id: string) => get<CharacterSummary[]>(`/api/projects/${id}/characters`),
  addCharacter: (id: string, name: string, role: string) =>
    send<CharacterSummary[]>(`/api/projects/${id}/characters`, "POST", { name, role }),
  generateCharacter: (id: string, body: {
    prompt: string; character_id?: string; hint_name?: string; hint_role?: string;
  }) => send<JobStatus>(`/api/projects/${id}/characters/generate`, "POST", body),
  getCharacterGeneratePreview: (id: string) =>
    getOptional<CharacterGeneratePreview>(`/api/projects/${id}/characters/generate/preview`),
  discardCharacterGeneratePreview: (id: string) =>
    del(`/api/projects/${id}/characters/generate/preview`),
  bibleDuplicates: (id: string, ai = false) =>
    get<BibleDuplicatesReport>(`/api/projects/${id}/story-bible/duplicates${ai ? "?ai=true" : ""}`),
  bibleDedupStatus: (id: string) =>
    get<BibleDedupStatus>(`/api/projects/${id}/story-bible/duplicates/status`),
  aiScanBibleDuplicates: (id: string) =>
    send<JobStatus>(`/api/projects/${id}/story-bible/duplicates/ai-scan`, "POST"),
  autoDedupeBible: (id: string) =>
    send<BibleAutoDedupeResult>(`/api/projects/${id}/story-bible/duplicates/auto-resolve`, "POST"),
  mergeBibleDuplicates: (id: string, body: BibleDedupeMerge) =>
    send<BibleAutoDedupeResult>(`/api/projects/${id}/story-bible/duplicates/merge`, "POST", body),
  deleteCharacter: (id: string, charId: string) =>
    del(`/api/projects/${id}/characters/${charId}`),
  plotThreads: (id: string) => get<PlotThreadSummary[]>(`/api/projects/${id}/plot-threads`),
  plotPanelIssues: (id: string) =>
    get<PlotPanelIssuesReport>(`/api/projects/${id}/plot-threads/panel-issues`),
  resolvePlotPanelIssue: (id: string, issueId: string) =>
    send<{ issue_id: string; log: string[] }>(
      `/api/projects/${id}/plot-threads/panel-issues/resolve`, "POST", { issue_id: issueId },
    ),
  autoResolvePlotPanelIssues: (id: string) =>
    send<{ resolved: number; log: string[] }>(
      `/api/projects/${id}/plot-threads/panel-issues/auto-resolve`, "POST",
    ),
  generatePlotThread: (id: string, threadId: string, body: { prompt?: string }) =>
    send<JobStatus>(`/api/projects/${id}/plot-threads/${threadId}/generate`, "POST", body),
  getPlotGeneratePreview: (id: string, threadId: string) =>
    getOptional<PlotGeneratePreview>(`/api/projects/${id}/plot-threads/${threadId}/generate/preview`),
  discardPlotGeneratePreview: (id: string, threadId: string) =>
    del(`/api/projects/${id}/plot-threads/${threadId}/generate/preview`),
  deletePlotThread: (id: string, threadId: string) =>
    del(`/api/projects/${id}/plot-threads/${threadId}`),
  deleteChapter: (id: string, n: number) => del(`/api/projects/${id}/chapters/${n}`),
  runPhase: (id: string, stage: string, params: Record<string, unknown> = {}) =>
    send<JobStatus>(`/api/projects/${id}/run`, "POST", { stage, params }),
  getJob: (jobId: string) => get<JobStatus>(`/api/jobs/${jobId}`),
  exportUrl: (id: string) => `${BASE}/api/projects/${id}/export`,
  exportProjectPackageUrl: (id: string) => `${BASE}/api/projects/${id}/export-package`,
  importProjectPackage: async (file: File): Promise<ProjectSummary> => {
    const resp = await fetch(`${BASE}/api/projects/import-package`, {
      method: "POST",
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${file.name}"`,
      },
      body: file,
    });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const j = await resp.json();
        if (j?.detail) detail = j.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json() as Promise<ProjectSummary>;
  },
  // snapshots
  snapshots: (id: string, n: number) =>
    get<SnapshotMeta[]>(`/api/projects/${id}/chapters/${n}/snapshots`),
  createSnapshot: (id: string, n: number, label: string) =>
    send<SnapshotMeta>(`/api/projects/${id}/chapters/${n}/snapshots`, "POST", { label }),
  getSnapshot: (id: string, n: number, sid: string) =>
    get<SnapshotText>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  restoreSnapshot: (id: string, n: number, sid: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}/restore`, "POST"),
  deleteSnapshot: (id: string, n: number, sid: string) =>
    del(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  // comments
  comments: (id: string, n: number) =>
    get<CommentItem[]>(`/api/projects/${id}/chapters/${n}/comments`),
  addComment: (id: string, n: number, body: string, quote: string) =>
    send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments`, "POST", { body, quote }),
  updateComment: (id: string, n: number, cid: string, resolved: boolean) =>
    send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments/${cid}`, "PATCH", { resolved }),
  deleteComment: (id: string, n: number, cid: string) =>
    del(`/api/projects/${id}/chapters/${n}/comments/${cid}`),
  systemPromptSettings: () => get<SystemPromptSettings>("/api/settings/system-prompt"),
  saveSystemPromptSettings: (prefix: string) =>
    send<SystemPromptSettings>("/api/settings/system-prompt", "PUT", { prefix, agents_dir: "" }),
  llmQueueSettings: () => get<LlmQueueSettings>("/api/settings/llm-queue"),
  saveLlmQueueSettings: (max_concurrent: number) =>
    send<LlmQueueSettings>("/api/settings/llm-queue", "PUT", { max_concurrent }),
  reorderLlmQueue: (order: string[]) =>
    send<LlmQueueSettings>("/api/settings/llm-queue/reorder", "POST", { order }),
  moveLlmQueueEntry: (entryId: string, position: "first" | "last") =>
    send<LlmQueueSettings>(`/api/settings/llm-queue/${entryId}/move`, "POST", { position }),
  cancelLlmQueueEntry: (entryId: string) =>
    send<LlmQueueSettings>(`/api/settings/llm-queue/${entryId}`, "DELETE"),
  restartNovelOs: () => send<RestartResult>("/api/system/restart", "POST"),
};

