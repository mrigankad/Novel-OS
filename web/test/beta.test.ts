import { describe, expect, it } from "vitest";
import { fmtDuration, paragraphs } from "@/lib/api/beta";

describe("beta reader helpers", () => {
  it("keeps paragraph offsets into the original text", () => {
    const text = "One.\n\nTwo here.\n  \nThree";
    const ps = paragraphs(text);
    expect(ps.map((p) => p.text)).toEqual(["One.", "Two here.", "Three"]);
    for (const p of ps) expect(text.slice(p.start, p.start + p.text.length)).toBe(p.text);
  });

  it("formats reading time", () => {
    expect(fmtDuration(0)).toBe("–");
    expect(fmtDuration(20)).toBe("20s");
    expect(fmtDuration(600)).toBe("10 min");
  });
});
