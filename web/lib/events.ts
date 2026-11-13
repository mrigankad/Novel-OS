"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

export type ServerEvent = { type: string; data: Record<string, unknown> };

/**
 * Subscribe to the project's live event stream (agents finishing runs, new
 * messages, chapter saves...). Every event invalidates the project's queries so
 * screens refresh without polling; pass onEvent for finer-grained handling.
 */
export function useProjectEvents(projectId: string | undefined, onEvent?: (e: ServerEvent) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!projectId || typeof EventSource === "undefined") return;
    const es = new EventSource(`/api/projects/${projectId}/events`);
    const handle = (type: string) => (msg: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(msg.data); } catch { /* keep-alive */ }
      onEvent?.({ type, data });
      const domain = type.split(".")[0];
      void qc.invalidateQueries({ queryKey: ["p", projectId, domain] });
      if (domain === "project" || domain === "chapter") {
        void qc.invalidateQueries({ queryKey: ["p", projectId], exact: true });
      }
    };
    const types = [
      "run.updated", "chapter.updated", "message.created", "memory.created",
      "codex.updated", "research.updated", "voice.updated", "publish.updated", "project.updated",
    ];
    const listeners = types.map((t) => [t, handle(t)] as const);
    listeners.forEach(([t, fn]) => es.addEventListener(t, fn));
    return () => es.close();
  }, [projectId, qc, onEvent]);
}
