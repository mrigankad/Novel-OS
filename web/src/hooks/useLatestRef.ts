import { useEffect, useRef, type RefObject } from "react";

/**
 * Keep a ref pointing at the most recent value without writing during render.
 *
 * Used for callbacks and state that long-lived listeners (editor plugins,
 * window events, timers) need to read at fire time rather than close over.
 * The write happens after commit, which is fine because every consumer here
 * reads the ref from an event that can only fire post-commit.
 */
export function useLatestRef<T>(value: T): RefObject<T> {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref;
}
