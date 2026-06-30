/** Local flags when a chapter has AI preview results awaiting review. */

const KEY = "novel-os:chapter-preview-pending";

type Store = Record<string, Record<string, boolean>>;

function readStore(): Store {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Store) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Store) {
  localStorage.setItem(KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent("novel-os:preview-pending"));
}

export function setChapterPreviewPending(projectId: string, chapter: number, pending: boolean) {
  const store = readStore();
  if (!store[projectId]) store[projectId] = {};
  if (pending) store[projectId][String(chapter)] = true;
  else delete store[projectId][String(chapter)];
  writeStore(store);
}

export function hasChapterPreviewPending(projectId: string, chapter: number): boolean {
  return Boolean(readStore()[projectId]?.[String(chapter)]);
}

export function projectChaptersWithPendingPreviews(projectId: string): Set<number> {
  const rows = readStore()[projectId] ?? {};
  return new Set(Object.keys(rows).filter((k) => rows[k]).map(Number));
}
