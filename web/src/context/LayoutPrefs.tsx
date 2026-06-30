import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "novel-os-show-library";

type LayoutPrefs = {
  showLibrary: boolean;
  setShowLibrary: (v: boolean) => void;
  toggleLibrary: () => void;
};

const LayoutPrefsContext = createContext<LayoutPrefs | null>(null);

function readStored(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "0" || raw === "false") return false;
  } catch {
    /* ignore */
  }
  return true;
}

export function LayoutPrefsProvider({ children }: { children: ReactNode }) {
  const [showLibrary, setShowLibraryState] = useState(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, showLibrary ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [showLibrary]);

  const setShowLibrary = useCallback((v: boolean) => setShowLibraryState(v), []);
  const toggleLibrary = useCallback(() => setShowLibraryState((s) => !s), []);

  return (
    <LayoutPrefsContext.Provider value={{ showLibrary, setShowLibrary, toggleLibrary }}>
      {children}
    </LayoutPrefsContext.Provider>
  );
}

export function useLayoutPrefs(): LayoutPrefs {
  const ctx = useContext(LayoutPrefsContext);
  if (!ctx) throw new Error("useLayoutPrefs must be used within LayoutPrefsProvider");
  return ctx;
}
