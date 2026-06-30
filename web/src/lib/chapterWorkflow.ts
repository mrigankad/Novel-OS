/** Track last-accessed chapter (binder) and last function per chapter (buttons). */

export type ChapterFunction =
  | "write"
  | "edit"
  | "validate"
  | "approve"
  | "regenerate"
  | "expand"
  | "outline-notes"
  | "outline-text"
  | "mine-plots"
  | "mine-characters"
  | "mine-bible"
  | "extract";

const STORAGE_KEY = "novel-os:chapter-workflow-v2";

type ProjectWorkflow = {
  /** Single chapter — blue dot in binder / board */
  lastAccessedChapter: number | null;
  /** Per-chapter last pipeline action — blue dot on buttons in that chapter only */
  lastFunctionByChapter: Record<string, ChapterFunction>;
};

type Store = Record<string, ProjectWorkflow>;

function emptyProject(): ProjectWorkflow {
  return { lastAccessedChapter: null, lastFunctionByChapter: {} };
}

function readStore(): Store {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent("novel-os:workflow"));
}

function projectStore(store: Store, projectId: string): ProjectWorkflow {
  if (!store[projectId]) store[projectId] = emptyProject();
  return store[projectId];
}

/** Opening a chapter — binder blue dot follows this (one chapter per project). */
export function recordChapterVisit(projectId: string, chapter: number) {
  const store = readStore();
  const p = projectStore(store, projectId);
  p.lastAccessedChapter = chapter;
  writeStore(store);
}

/** Running a pipeline action — updates button marker for this chapter + last accessed. */
export function recordChapterFunction(
  projectId: string,
  chapter: number,
  fn: ChapterFunction,
) {
  const store = readStore();
  const p = projectStore(store, projectId);
  p.lastAccessedChapter = chapter;
  p.lastFunctionByChapter[String(chapter)] = fn;
  writeStore(store);
}

export function getLastAccessedChapter(projectId: string): number | null {
  const ch = readStore()[projectId]?.lastAccessedChapter;
  return ch != null ? ch : null;
}

export function getChapterFunction(
  projectId: string,
  chapter: number,
): ChapterFunction | null {
  return readStore()[projectId]?.lastFunctionByChapter[String(chapter)] ?? null;
}

export const CHAPTER_FUNCTION_LABELS: Record<ChapterFunction, string> = {
  write: "Generate Draft",
  edit: "Revise",
  validate: "Validate",
  approve: "Approve",
  regenerate: "Regenerate",
  expand: "Expand placeholders",
  "outline-notes": "Outline from notes",
  "outline-text": "Outline from text",
  "mine-plots": "Mine plots",
  "mine-characters": "Mine characters",
  "mine-bible": "Mine story bible",
  extract: "Extract",
};
