import { useEffect, useState } from "react";
import {
  getChapterFunction,
  getLastAccessedChapter,
} from "../lib/chapterWorkflow";

/** Re-render when workflow markers change in localStorage. */
export function useWorkflowMarkers(projectId: string, chapter?: number) {
  const [, tick] = useState(0);

  useEffect(() => {
    const bump = () => tick((n) => n + 1);
    window.addEventListener("novel-os:workflow", bump);
    window.addEventListener("novel-os:preview-pending", bump);
    return () => {
      window.removeEventListener("novel-os:workflow", bump);
      window.removeEventListener("novel-os:preview-pending", bump);
    };
  }, []);

  void tick;

  return {
    lastAccessedChapter: getLastAccessedChapter(projectId),
    lastFunction: chapter != null ? getChapterFunction(projectId, chapter) : null,
  };
}
