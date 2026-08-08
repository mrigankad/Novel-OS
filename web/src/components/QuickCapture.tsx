import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api } from "../api/client";
import { useToast } from "./toastContext";

/**
 * Quick capture (design spec §4.7).
 *
 * Job 19 of writing a novel: recording what you will fix later *without*
 * stopping to fix it now. Every working novelist keeps a spiral notebook for
 * exactly this, and every tool that makes you leave the page to write a note
 * has broken the flow the note was supposed to protect.
 *
 * ⌘. opens one line, Enter files it against the current chapter, focus goes
 * straight back to the manuscript. The note lands as an ordinary comment, so it
 * shows up in the Inspector and in Revise mode with everything else - a
 * separate "notes" store would just be a second inbox to forget about.
 */
export default function QuickCapture({
  projectId,
  chapterNumber,
  onCaptured,
}: {
  projectId: string;
  chapterNumber: number;
  onCaptured?: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // Where focus was before the box opened, so it can be handed straight back.
  const returnTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        returnTo.current = document.activeElement as HTMLElement | null;
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    setNote("");
    // The whole point is not losing your place: put the cursor back.
    returnTo.current?.focus();
  }

  async function save() {
    const body = note.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      await api.addComment(projectId, chapterNumber, body, "", null, null);
      toast("Noted", "success");
      onCaptured?.();
      close();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
      // Keep the box open and the words in it, so nothing is lost to a failure.
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.16 }}
          className="fixed bottom-6 left-1/2 z-[80] w-[min(92vw,520px)] -translate-x-1/2"
        >
          <div className="flex items-center gap-2 rounded-2xl border border-[rgba(74,91,133,0.16)] bg-white/95 p-2 shadow-[0_18px_44px_rgba(40,52,90,0.2)] backdrop-blur-md">
            <span className="shrink-0 pl-1.5 text-[11px] font-semibold uppercase tracking-wide text-paper-muted">
              Note
            </span>
            <input
              ref={inputRef}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { e.preventDefault(); void save(); }
                if (e.key === "Escape") { e.preventDefault(); close(); }
              }}
              placeholder="Fix later: her coat was grey in ch.3…"
              aria-label="Quick note"
              disabled={busy}
              className="min-w-0 flex-1 bg-transparent px-1 py-1.5 text-[13.5px] text-ink-text outline-none placeholder:text-paper-muted"
            />
            <span className="shrink-0 pr-1 text-[11px] text-paper-muted">↵ to file</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
