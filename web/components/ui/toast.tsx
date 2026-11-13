"use client";

import { clsx } from "clsx";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Tone = "info" | "success" | "error";
type Toast = { id: number; message: string; tone: Tone };

const Ctx = createContext<(message: string, tone?: Tone) => void>(() => {});

export function Toaster({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, message, tone }]);
    setTimeout(() => setItems((xs) => xs.filter((t) => t.id !== id)), 3800);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-5 left-4 right-4 z-50 items-end sm:left-auto sm:right-5 flex flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={clsx(
            "pointer-events-auto rounded-[10px] px-4 py-2.5 text-[13px] font-medium shadow-[0_8px_24px_rgba(0,0,0,0.16)]",
            t.tone === "error" ? "bg-fail text-on-accent" : t.tone === "success" ? "bg-inverse text-on-inverse" : "bg-paper text-ink ring-1 ring-rule",
          )}>
            {t.message}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
