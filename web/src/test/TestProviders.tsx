import { type ReactNode } from "react";
import { LayoutPrefsProvider } from "../context/LayoutPrefs";

/** Wrap route components that call useLayoutPrefs in tests. */
export function TestProviders({ children }: { children: ReactNode }) {
  return <LayoutPrefsProvider>{children}</LayoutPrefsProvider>;
}
