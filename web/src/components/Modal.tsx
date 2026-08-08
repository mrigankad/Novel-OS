import { useEffect, type ReactNode } from "react";
import { motion, AnimatePresence } from "motion/react";

export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div
            className="absolute inset-0 bg-[#0c3bb8]/35 backdrop-blur-[6px]"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.32, ease: [0.2, 0.9, 0.2, 1] }}
            className="glass-shell relative flex max-h-[min(92dvh,100%)] w-full max-w-lg flex-col overflow-hidden !rounded-t-[28px] !rounded-b-none p-2.5 sm:max-h-[min(88dvh,640px)] sm:!rounded-[28px] sm:p-3"
          >
            <div className="glass-panel flex min-h-0 flex-1 flex-col overflow-hidden p-0">
              <h2 className="shrink-0 px-5 pb-3 pt-5 font-display text-[20px] font-semibold tracking-[-0.035em] text-ink-text sm:px-7 sm:pt-6 sm:text-[22px]">
                {title}
              </h2>
              <div
                className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5 sm:px-7 sm:pb-7 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              >
                {children}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-[12px] font-medium tracking-[-0.01em] text-ink-muted">
        {label}
      </span>
      {children}
    </label>
  );
}

export const fieldClass =
  "w-full rounded-full border border-[rgba(96,112,153,0.17)] bg-white/60 px-4 py-2.5 text-[14px] font-medium text-ink-text shadow-[inset_0_1px_3px_rgba(48,62,98,0.06)] placeholder:text-paper-muted focus:border-[rgba(104,103,234,0.38)] focus:bg-white focus:outline-none focus:shadow-[0_0_0_5px_rgba(104,103,234,0.09)]";

/** Multi-line fields more inset padding so text clears the rounded corners. */
export const textareaClass =
  "w-full min-h-[72px] resize-y rounded-2xl border border-[rgba(96,112,153,0.17)] bg-white/60 px-4 py-3.5 text-[14px] font-medium leading-relaxed text-ink-text shadow-[inset_0_1px_3px_rgba(48,62,98,0.06)] placeholder:text-paper-muted focus:border-[rgba(104,103,234,0.38)] focus:bg-white focus:outline-none focus:shadow-[0_0_0_5px_rgba(104,103,234,0.09)] sm:min-h-[96px]";
