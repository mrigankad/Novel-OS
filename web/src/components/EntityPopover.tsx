import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { api, type CodexEntry, type RelationshipEdge } from "../api/client";
import Icon from "./Icon";

/** Left-click popover on a Codex mention in Final (R1). */
export default function EntityPopover({
  open,
  x,
  y,
  entry,
  projectId,
  onClose,
  onAddRelationship,
}: {
  open: boolean;
  x: number;
  y: number;
  entry: CodexEntry | null;
  projectId: string;
  onClose: () => void;
  onAddRelationship?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState<RelationshipEdge[]>([]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const showsBonds = open && entry?.entry_type === "character";

  useEffect(() => {
    if (!showsBonds || !entry) return;
    let cancelled = false;
    api.relationships(projectId, entry.id)
      .then((list) => { if (!cancelled) setEdges(list.slice(0, 3)); })
      .catch(() => { if (!cancelled) setEdges([]); });
    return () => { cancelled = true; };
  }, [showsBonds, entry, projectId]);

  // Derived rather than cleared in the effect, so bonds from the previously
  // shown entity can never leak into this one's first paint.
  const visibleEdges = showsBonds ? edges : [];

  const src = api.assetUrl(entry?.portrait_url);
  const left = Math.min(x, typeof window !== "undefined" ? window.innerWidth - 280 : x);
  const top = Math.min(y + 8, typeof window !== "undefined" ? window.innerHeight - 220 : y);

  return (
    <AnimatePresence>
      {open && entry && (
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 6, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 4, scale: 0.96 }}
          transition={{ duration: 0.16 }}
          style={{ left, top }}
          className="fixed z-[75] w-[260px] overflow-hidden rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/95 p-3 shadow-[0_18px_40px_rgba(40,52,90,0.18)] backdrop-blur-md"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-[#eeedff] to-[#e7e7ff] font-display text-[15px] font-semibold text-[var(--color-violet)]">
              {src ? <img src={src} alt="" className="h-full w-full object-cover" /> : entry.name.charAt(0)}
            </span>
            <div className="min-w-0">
              <p className="truncate font-display text-[15px] font-semibold text-ink-text">{entry.name}</p>
              <p className="text-[12px] capitalize text-ink-muted">
                {entry.entry_type === "worldbuilding" ? "World" : entry.entry_type}
                {entry.role ? ` · ${entry.role}` : ""}
              </p>
            </div>
          </div>
          {entry.summary ? (
            <p className="mt-2 line-clamp-3 text-[12.5px] leading-relaxed text-ink-muted">{entry.summary}</p>
          ) : null}
          {visibleEdges.length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-[rgba(74,91,133,0.1)] pt-2">
              {visibleEdges.map((e) => {
                const other =
                  e.source_id === entry.id
                    ? (e.target_name || e.target_id)
                    : (e.source_name || e.source_id);
                return (
                  <li key={e.id} className="truncate text-[12px] text-ink-muted">
                    <span className="capitalize">{e.label}</span>
                    {" · "}
                    <span className="font-medium text-ink-text">{other}</span>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Link
              to={`/projects/${projectId}?codex=${entry.id}`}
              onClick={onClose}
              className="btn-secondary inline-flex items-center gap-1 px-2.5 py-1 text-[12px]"
            >
              <Icon name="users" className="h-3 w-3" /> Open Codex
            </Link>
            <Link
              to={`/projects/${projectId}/chart`}
              onClick={onClose}
              className="btn-ghost inline-flex items-center gap-1 px-2.5 py-1 text-[12px]"
            >
              <Icon name="waypoints" className="h-3 w-3" /> Chart
            </Link>
            {onAddRelationship && (
              <button type="button" onClick={() => { onAddRelationship(); onClose(); }} className="btn-ghost px-2.5 py-1 text-[12px]">
                Link…
              </button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
