import { useRef, useState } from "react";
import { api, type CodexEntry, type MediaKind } from "../api/client";
import Icon from "./Icon";
import { useToast } from "./toastContext";

function mediaKindFor(entryType: string): MediaKind {
  if (entryType === "location") return "location";
  if (entryType === "character") return "portrait";
  return "general";
}

/** Upload / replace / clear a Codex entry image (character portrait, location shot, etc.). */
export default function CodexImageButton({
  projectId,
  entry,
  onUpdated,
  size = "md",
  shape = "circle",
  label,
}: {
  projectId: string;
  entry: CodexEntry;
  onUpdated: () => void;
  size?: "sm" | "md" | "lg";
  shape?: "circle" | "rounded";
  label?: string;
}) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const src = api.assetUrl(entry.portrait_url);
  const dim = size === "lg" ? "h-28 w-28" : size === "sm" ? "h-10 w-10" : "h-14 w-14";
  const radius = shape === "circle" ? "rounded-full" : "rounded-2xl";

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try {
      const media = await api.uploadMedia(
        projectId,
        file,
        mediaKindFor(entry.entry_type),
        entry.name,
      );
      await api.setPortrait(projectId, entry.id, media.id, entry.entry_type);
      toast("Image saved", "success");
      onUpdated();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function clear() {
    setBusy(true);
    try {
      await api.setPortrait(projectId, entry.id, "", entry.entry_type);
      toast("Image removed", "success");
      onUpdated();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  const emptyHint =
    entry.entry_type === "location" ? "Add place photo"
      : entry.entry_type === "item" ? "Add item image"
        : entry.entry_type === "worldbuilding" ? "Add reference"
          : "Add portrait";

  return (
    <div className="flex flex-col items-center gap-1.5">
      <button
        type="button"
        title={src ? "Replace image" : emptyHint}
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        className={`group relative flex ${dim} shrink-0 items-center justify-center overflow-hidden ${radius} bg-gradient-to-br from-[#eeedff] to-[#e7e7ff] text-[var(--color-violet)] transition hover:ring-2 hover:ring-[rgba(104,103,234,0.35)] disabled:opacity-50`}
      >
        {src ? (
          <img src={src} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="flex flex-col items-center gap-0.5 px-1">
            <Icon name="image" className="h-4 w-4 opacity-70" />
            {size === "lg" && (
              <span className="text-center text-[10px] font-medium leading-tight text-ink-muted">
                {emptyHint}
              </span>
            )}
            {size !== "lg" && (
              <span className="font-display text-[15px] font-semibold">
                {entry.name.charAt(0).toUpperCase()}
              </span>
            )}
          </span>
        )}
        <span className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition group-hover:opacity-100">
          <Icon name="upload" className="h-4 w-4 text-white" />
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        onChange={(e) => void onFile(e.target.files?.[0])}
      />
      {(label || src) && (
        <div className="flex items-center gap-2">
          {label && (
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="text-[11.5px] font-medium text-[var(--color-violet)] hover:underline disabled:opacity-40"
            >
              {src ? "Replace" : label}
            </button>
          )}
          {src && (
            <button
              type="button"
              disabled={busy}
              onClick={() => void clear()}
              className="text-[11.5px] text-ink-muted hover:text-[#c85177] disabled:opacity-40"
            >
              Remove
            </button>
          )}
        </div>
      )}
    </div>
  );
}
