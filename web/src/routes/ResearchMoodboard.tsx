import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { api, type MediaItem, type ProjectDetail } from "../api/client";
import Scene from "../components/Scene";
import Icon from "../components/Icon";
import { useToast } from "../components/toastContext";
import { useConfirm } from "../components/confirmContext";

/** Research moodboard — images, notes, scrap references (PLAN.md P4). */
export default function ResearchMoodboard() {
  const { id = "" } = useParams();
  const toast = useToast();
  const confirm = useConfirm();
  const fileRef = useRef<HTMLInputElement>(null);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftAlt, setDraftAlt] = useState("");

  const load = useCallback(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.media(id, "research").then(setItems).catch(() => setItems([]));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const item = await api.uploadMedia(id, file, "research", file.name.replace(/\.[^.]+$/, ""));
        setItems((prev) => {
          if (prev.some((p) => p.id === item.id)) return prev;
          return [item, ...prev];
        });
      }
      toast("Added to research board", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function saveAlt(item: MediaItem) {
    try {
      const updated = await api.updateMedia(id, item.id, { alt: draftAlt.trim() });
      setItems((prev) => prev.map((p) => (p.id === item.id ? updated : p)));
      setEditingId(null);
      toast("Note saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function remove(item: MediaItem) {
    const ok = await confirm({
      title: "Remove from research",
      message: "Delete this image from the moodboard?",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.deleteMedia(id, item.id);
      setItems((prev) => prev.filter((p) => p.id !== item.id));
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  if (error) {
    return (
      <Scene>
        <div className="px-10 py-12 text-[13px] text-ink-muted">Failed to load: {error}</div>
      </Scene>
    );
  }

  return (
    <Scene>
      <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
          className="glass-shell p-3 sm:p-4"
        >
          <div className="glass-panel px-6 py-8 sm:px-10 sm:py-10">
            <Link
              to={`/projects/${id}`}
              className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition-colors hover:text-[var(--color-violet)]"
            >
              ← {project?.title || "Project"}
            </Link>

            <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Studio</p>
                <h1 className="font-display text-[32px] font-semibold tracking-tight text-ink-text">
                  Research
                </h1>
                <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-ink-muted">
                  Moodboard for reference images, places, and scrap notes. Drop files or upload.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  multiple
                  className="hidden"
                  onChange={(e) => void onFiles(e.target.files)}
                />
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                  className="btn-primary disabled:opacity-40"
                >
                  {uploading ? "Uploading…" : "Add images"}
                </button>
              </div>
            </header>

            <div
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }}
              onDrop={(e) => {
                e.preventDefault();
                void onFiles(e.dataTransfer.files);
              }}
              className={`rounded-[24px] border border-dashed border-[rgba(74,91,133,0.2)] bg-white/40 px-6 py-10 transition-colors ${
                items.length === 0 ? "" : "mb-6"
              }`}
            >
              {items.length === 0 ? (
                <div className="text-center">
                  <Icon name="image" className="mx-auto h-8 w-8 text-paper-muted" />
                  <p className="mt-3 font-display text-[16px] text-ink-text">Empty board</p>
                  <p className="mt-1 text-[13px] text-ink-muted">
                    Drop reference photos here, or use Add images.
                  </p>
                </div>
              ) : (
                <p className="text-center text-[12.5px] text-ink-muted">
                  Drop more images anywhere on this board
                </p>
              )}
            </div>

            {items.length > 0 && (
              <div className="columns-1 gap-4 sm:columns-2 lg:columns-3">
                {items.map((item) => (
                  <article
                    key={item.id}
                    className="mb-4 break-inside-avoid overflow-hidden rounded-[22px] border border-[rgba(74,91,133,0.12)] bg-white/70 shadow-[0_8px_24px_rgba(48,62,98,0.06)]"
                  >
                    <img
                      src={api.mediaUrl(item)}
                      alt={item.alt || item.filename}
                      className="block w-full object-cover"
                      loading="lazy"
                    />
                    <div className="space-y-2 p-3.5">
                      {editingId === item.id ? (
                        <>
                          <textarea
                            value={draftAlt}
                            onChange={(e) => setDraftAlt(e.target.value)}
                            rows={2}
                            className="w-full rounded-xl border border-[rgba(96,112,153,0.16)] bg-white px-3 py-2 text-[13px] text-ink-text"
                            placeholder="Caption or research note…"
                          />
                          <div className="flex gap-2">
                            <button type="button" className="btn-primary" onClick={() => void saveAlt(item)}>
                              Save
                            </button>
                            <button type="button" className="btn-ghost" onClick={() => setEditingId(null)}>
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p className="text-[13px] leading-relaxed text-ink-text">
                            {item.alt || <span className="text-ink-muted">No note yet</span>}
                          </p>
                          <div className="flex flex-wrap gap-3 text-[12px] font-medium">
                            <button
                              type="button"
                              className="text-[var(--color-violet)] hover:underline"
                              onClick={() => {
                                setEditingId(item.id);
                                setDraftAlt(item.alt || "");
                              }}
                            >
                              Edit note
                            </button>
                            <button
                              type="button"
                              className="text-ink-muted hover:text-ink"
                              onClick={() => void remove(item)}
                            >
                              Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </Scene>
  );
}
