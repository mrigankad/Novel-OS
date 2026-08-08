import { useCallback, useState, type ReactNode } from "react";
import { ToastCtx, type ToastTone as Tone } from "./toastContext";

interface Toast {
  id: number;
  message: string;
  tone: Tone;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  return (
    <ToastCtx.Provider value={push}>
      {children}
      {/* polite live region announced to screen readers, visible to all */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-2xl border px-3.5 py-2.5 text-[12.5px] font-medium shadow-[0_12px_32px_rgba(48,62,98,0.16)] backdrop-blur-xl ${
              t.tone === "error"
                ? "border-[rgba(200,80,100,0.35)] bg-[rgba(255,240,244,0.92)] text-[#a8324a]"
                : t.tone === "success"
                  ? "border-[rgba(104,103,234,0.28)] bg-[rgba(255,255,255,0.88)] text-ink-text"
                  : "border-[rgba(74,91,133,0.16)] bg-[rgba(255,255,255,0.86)] text-ink-text"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
