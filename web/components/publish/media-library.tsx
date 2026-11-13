"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { ChevronLeft, ChevronRight, ImagePlus, Link2, Sparkles, Trash2, Upload, X } from "lucide-react";
import { GenerateImageSheet } from "@/components/images/generate-image-sheet";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { MEDIA_KINDS, mediaApi, publishKeys, type Media, type MediaKind } from "@/lib/api/publish";

const ACCEPT = "image/png,image/jpeg,image/webp,image/gif,image/svg+xml";
const MAX = 15 * 1024 * 1024;
const S = 1.75;

export function MediaLibrary({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<MediaKind | "">("");
  const [generating, setGenerating] = useState(false);
  const [tag, setTag] = useState("");
  const [url, setUrl] = useState("");
  const [drag, setDrag] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const all = useQuery({ queryKey: publishKeys.media(projectId), queryFn: () => mediaApi.list(projectId) });
  const items = (all.data ?? []).filter(
    (m) => (!kind || m.kind === kind) && (!tag || m.tags.some((t) => t.toLowerCase() === tag.toLowerCase())),
  );
  const tags = Array.from(new Set((all.data ?? []).flatMap((m) => m.tags))).sort();
  const refresh = () => qc.invalidateQueries({ queryKey: publishKeys.media(projectId) });

  const upload = useMutation({
    mutationFn: (files: File[]) => mediaApi.upload(projectId, files, kind || "image"),
    onSuccess: (rows) => {
      const dupes = rows.filter((r) => r.duplicate).length;
      toast(dupes ? `${rows.length - dupes} added, ${dupes} already in the library` : `${rows.length} added`, "success");
      void refresh();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const importUrl = useMutation({
    mutationFn: () => mediaApi.importUrl(projectId, url.trim()),
    onSuccess: (m) => { setUrl(""); toast(m.duplicate ? "Already in the library" : "Imported", "success"); void refresh(); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const send = (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    const big = files.filter((f) => f.size > MAX);
    if (big.length) toast(`${big.map((f) => f.name).join(", ")} over 15 MB, skipped`, "error");
    const ok = files.filter((f) => f.size <= MAX);
    if (ok.length) upload.mutate(ok);
  };

  return (
    <Page wide>
      <PageHeader
        eyebrow="Ship"
        title="Media"
        description="Portraits, maps, mood boards and cover art. Everything here can go on the cover or into the Codex."
        actions={<>
          <Button variant="ai" onClick={() => setGenerating(true)}><Sparkles size={16} strokeWidth={S} />Generate</Button>
          <Button onClick={() => fileRef.current?.click()}><Upload size={16} strokeWidth={S} />Upload</Button>
        </>}
      />
      <input ref={fileRef} type="file" accept={ACCEPT} multiple hidden onChange={(e) => { send(e.target.files); e.target.value = ""; }} />

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files); }}
        className={clsx(
          "mt-8 flex flex-col items-center justify-center gap-2 rounded-[16px] border border-dashed px-6 py-8 text-center transition-colors",
          drag ? "border-gall bg-wash" : "border-rule-strong bg-sheet",
        )}
      >
        <ImagePlus size={22} strokeWidth={S} className="text-body" />
        <p className="text-[14px] text-ink">
          {upload.isPending ? "Uploading…" : "Drop images here"}
          <span className="text-muted"> · png, jpg, webp, gif or svg, up to 15 MB each</span>
        </p>
        <form
          className="mt-2 flex w-full max-w-lg items-center gap-2"
          onSubmit={(e) => { e.preventDefault(); if (url.trim()) importUrl.mutate(); }}
        >
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Or paste an image URL" aria-label="Image URL" />
          <Button type="submit" variant="secondary" disabled={!url.trim() || importUrl.isPending}>
            <Link2 size={16} strokeWidth={S} />Import
          </Button>
        </form>
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-2">
        <Chip active={!kind} onClick={() => setKind("")}>All</Chip>
        {MEDIA_KINDS.map((k) => (
          <Chip key={k} active={kind === k} onClick={() => setKind(k)}>{k}</Chip>
        ))}
        {tags.length > 0 && <span className="mx-2 h-5 w-px bg-rule-strong" />}
        {tags.map((t) => (
          <Chip key={t} active={tag === t} onClick={() => setTag(tag === t ? "" : t)}>#{t}</Chip>
        ))}
      </div>

      <div className="mt-6">
        {all.isLoading ? (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState title={all.data?.length ? "Nothing matches" : "No images yet"}
            body={all.data?.length ? "Clear the filters to see everything." : "Upload art, a map or a portrait to start the library."} />
        ) : (
          <div className="columns-2 gap-4 md:columns-3 xl:columns-4">
            {items.map((m, i) => (
              <figure key={m.id} className="mb-4 break-inside-avoid">
                <button type="button" onClick={() => setOpen(i)} className="block w-full overflow-hidden rounded-[10px] bg-sheet">
                  <img src={m.url} alt={m.caption || m.filename} loading="lazy" className="w-full object-cover transition-transform duration-300 hover:scale-[1.02]" />
                </button>
                <figcaption className="mt-2 flex items-baseline justify-between gap-2">
                  <span className="truncate text-[13px] text-ink">{m.caption || m.filename}</span>
                  <span className="shrink-0 text-[11px] text-muted">{m.kind}{m.width ? ` · ${m.width}×${m.height}` : ""}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </div>

      {open !== null && items[open] && (
        <Lightbox
          key={items[open].id}
          media={items[open]}
          onClose={() => setOpen(null)}
          onPrev={open > 0 ? () => setOpen(open - 1) : undefined}
          onNext={open < items.length - 1 ? () => setOpen(open + 1) : undefined}
          onChanged={refresh}
        />
      )}
      <GenerateImageSheet projectId={projectId} open={generating} onClose={() => setGenerating(false)}
        kind={kind === "cover" || kind === "portrait" || kind === "map" ? kind : "image"} onDone={() => refresh()} />
    </Page>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} className={clsx(
      "h-8 rounded-full px-3 text-[13px] font-medium capitalize transition-colors",
      active ? "bg-ink text-white" : "bg-sheet text-body hover:text-ink",
    )}>{children}</button>
  );
}

function Lightbox({ media, onClose, onPrev, onNext, onChanged }: {
  media: Media; onClose: () => void; onPrev?: () => void; onNext?: () => void; onChanged: () => void;
}) {
  const toast = useToast();
  const [caption, setCaption] = useState(media.caption);
  const [tags, setTags] = useState(media.tags.join(", "));
  const save = useMutation({
    mutationFn: (body: Parameters<typeof mediaApi.update>[1]) => mediaApi.update(media.id, body),
    onSuccess: () => onChanged(),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const del = useMutation({
    mutationFn: () => mediaApi.remove(media.id),
    onSuccess: () => { onClose(); onChanged(); toast("Deleted", "success"); },
  });

  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.target as HTMLElement)?.tagName === "INPUT") return;
    if (e.key === "Escape") onClose();
    if (e.key === "ArrowLeft") onPrev?.();
    if (e.key === "ArrowRight") onNext?.();
  }, [onClose, onPrev, onNext]);
  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);

  const commit = () => save.mutate({ caption, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) });

  return (
    <div className="fixed inset-0 z-40 flex bg-[rgba(20,19,26,0.88)]" role="dialog" aria-modal="true" aria-label={media.filename}>
      <div className="relative flex flex-1 items-center justify-center p-10" onClick={onClose}>
        <img src={media.url} alt={media.caption || media.filename} className="max-h-full max-w-full object-contain" onClick={(e) => e.stopPropagation()} />
        {onPrev && <NavBtn side="left" onClick={onPrev}><ChevronLeft size={20} strokeWidth={S} /></NavBtn>}
        {onNext && <NavBtn side="right" onClick={onNext}><ChevronRight size={20} strokeWidth={S} /></NavBtn>}
      </div>
      <aside className="flex w-[340px] shrink-0 flex-col gap-5 bg-paper p-6">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-display text-[20px] font-bold tracking-[-0.02em] text-ink">{media.filename}</p>
            <p className="text-[12px] text-muted">{media.width}×{media.height} · {(media.size / 1024).toFixed(0)} KB</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="text-body hover:text-ink"><X size={18} strokeWidth={S} /></button>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-semibold text-ink">Caption</span>
          <Input value={caption} onChange={(e) => setCaption(e.target.value)} onBlur={commit} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-semibold text-ink">Tags <span className="font-normal text-muted">· comma separated</span></span>
          <Input value={tags} onChange={(e) => setTags(e.target.value)} onBlur={commit} />
        </label>
        <div>
          <span className="text-[12px] font-semibold text-ink">Kind</span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {MEDIA_KINDS.map((k) => (
              <Chip key={k} active={media.kind === k} onClick={() => save.mutate({ kind: k })}>{k}</Chip>
            ))}
          </div>
        </div>
        <div className="mt-auto">
          <Button variant="danger" size="sm" onClick={() => del.mutate()} disabled={del.isPending}>
            <Trash2 size={14} strokeWidth={S} />Delete image
          </Button>
        </div>
      </aside>
    </div>
  );
}

function NavBtn({ side, onClick, children }: { side: "left" | "right"; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={clsx("absolute top-1/2 -translate-y-1/2 rounded-full bg-paper/90 p-2 text-ink hover:bg-paper", side === "left" ? "left-4" : "right-4")}>
      {children}
    </button>
  );
}
