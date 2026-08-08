import { useCallback, useEffect, useState } from "react";
import {
  MODE_EVENT,
  getStudioMode,
  setStudioMode,
  type StudioMode,
} from "../lib/studioMode";

/**
 * Current studio mode, kept in step across every mounted surface.
 *
 * Backed by a window event rather than context so the switcher in the chrome
 * and the chapter surface stay in sync without threading a provider through
 * the router.
 */
export function useStudioMode(): [StudioMode, (m: StudioMode) => void] {
  const [mode, setMode] = useState<StudioMode>(getStudioMode);

  useEffect(() => {
    const onChange = (e: Event) => {
      const next = (e as CustomEvent<StudioMode>).detail;
      if (next) setMode(next);
    };
    window.addEventListener(MODE_EVENT, onChange);
    // Another tab editing the same manuscript should not drift out of step.
    const onStorage = () => setMode(getStudioMode());
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(MODE_EVENT, onChange);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const change = useCallback((next: StudioMode) => setStudioMode(next), []);
  return [mode, change];
}
