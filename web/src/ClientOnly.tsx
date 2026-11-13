"use client";
import dynamic from "next/dynamic";
import type { ReactNode } from "react";

/**
 * The Studio is a browser app (editor, localStorage, matchMedia), so the shell
 * renders on the client only. Pages stream in as children.
 */
const Shell = dynamic(() => import("./Shell"), {
  ssr: false,
  loading: () => <div className="h-full bg-[var(--color-sheet)]" />,
});

export default function ClientOnly({ children }: { children: ReactNode }) {
  return <Shell>{children}</Shell>;
}
