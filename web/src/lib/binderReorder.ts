/** Compute the sibling index to pass to `POST …/binder/move` after a drag. */

export type DropPlace = "before" | "after";

/**
 * Map a drag from `fromIndex` onto `overIndex` (before/after that sibling)
 * into the final insert index the binder move API expects.
 * Returns null when the order would not change.
 */
export function reorderIndex(
  fromIndex: number,
  overIndex: number,
  place: DropPlace,
): number | null {
  if (fromIndex < 0 || overIndex < 0) return null;
  let insert = place === "after" ? overIndex + 1 : overIndex;
  if (fromIndex < insert) insert -= 1;
  if (insert === fromIndex) return null;
  return Math.max(0, insert);
}

/** Prefer before/after from pointer Y within the drop target. */
export function dropPlaceFromY(clientY: number, rect: DOMRect): DropPlace {
  const mid = rect.top + rect.height / 2;
  return clientY < mid ? "before" : "after";
}
