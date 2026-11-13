"use client";

import { useSyncExternalStore } from "react";

/** Ids of agent messages that are still being written (message.delta seen, no message.updated yet). */
const live = new Set<string>();
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

export const streaming = {
  start(id: string) { if (!live.has(id)) { live.add(id); emit(); } },
  end(id: string) { if (live.delete(id)) emit(); },
};

export function useIsStreaming(id: string): boolean {
  return useSyncExternalStore(
    (cb) => { subs.add(cb); return () => { subs.delete(cb); }; },
    () => live.has(id),
    () => false,
  );
}
