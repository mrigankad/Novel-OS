import type { ContinuityFinding } from "../api/client";

export type ChapterContinuityBadge = {
  critical: number;
  warning: number;
};

/** Roll continuity findings up to per-chapter counts for the board badges. */
export function badgesFromFindings(
  findings: ContinuityFinding[] | undefined,
): Record<number, ChapterContinuityBadge> {
  const map: Record<number, ChapterContinuityBadge> = {};
  for (const f of findings ?? []) {
    if (f.chapter == null) continue;
    const slot = map[f.chapter] ?? { critical: 0, warning: 0 };
    if (f.severity === "critical") slot.critical += 1;
    else if (f.severity === "warning") slot.warning += 1;
    map[f.chapter] = slot;
  }
  return map;
}
