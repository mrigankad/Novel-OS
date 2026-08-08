import { describe, expect, it } from "vitest";
import { dropPlaceFromY, reorderIndex } from "../lib/binderReorder";

describe("reorderIndex", () => {
  it("moves later when dropping after a later sibling", () => {
    // [A B C] drag A after B → [B A C] → index 1
    expect(reorderIndex(0, 1, "after")).toBe(1);
  });

  it("moves earlier when dropping before an earlier sibling", () => {
    // [A B C] drag C before A → [C A B] → index 0
    expect(reorderIndex(2, 0, "before")).toBe(0);
  });

  it("returns null when drop would leave order unchanged", () => {
    expect(reorderIndex(1, 1, "before")).toBe(null);
    expect(reorderIndex(1, 0, "after")).toBe(null);
  });

  it("handles drop before next sibling as no-op", () => {
    // Drag A before B → already before B
    expect(reorderIndex(0, 1, "before")).toBe(null);
  });
});

describe("dropPlaceFromY", () => {
  it("splits the target at mid height", () => {
    const rect = { top: 100, height: 40 } as DOMRect;
    expect(dropPlaceFromY(110, rect)).toBe("before");
    expect(dropPlaceFromY(130, rect)).toBe("after");
  });
});
