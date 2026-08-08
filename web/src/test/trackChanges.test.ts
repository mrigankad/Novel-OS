import { describe, expect, test } from "vitest";
import {
  SUGGESTION_DELETE,
  SUGGESTION_INSERT,
  acceptAllSuggestions,
  acceptSuggestion,
  acceptedDoc,
  hasSuggestions,
  listSuggestions,
  newSuggestionId,
  rejectAllSuggestions,
  rejectSuggestion,
} from "../lib/trackChanges";
import type { PMDoc } from "../lib/richText";

function text(t: string, mark?: { type: string; id: string; author?: string }) {
  return mark
    ? {
        type: "text",
        text: t,
        marks: [
          { type: mark.type, attrs: { id: mark.id, author: mark.author ?? "A", at: "" } },
        ],
      }
    : { type: "text", text: t };
}

function doc(...content: unknown[]): PMDoc {
  return { type: "doc", content: [{ type: "paragraph", content }] } as PMDoc;
}

function flatten(d: PMDoc): string {
  const out: string[] = [];
  const walk = (n: { type?: string; text?: string; content?: unknown[] }) => {
    if (n.type === "text") out.push(n.text || "");
    for (const c of (n.content || []) as typeof n[]) walk(c);
  };
  walk(d as never);
  return out.join("");
}

describe("listSuggestions", () => {
  test("returns nothing for plain prose", () => {
    expect(listSuggestions(doc(text("She left.")))).toEqual([]);
    expect(hasSuggestions(doc(text("She left.")))).toBe(false);
  });

  test("reports kind, author and text", () => {
    const d = doc(
      text("She left "),
      text("quietly", { type: SUGGESTION_DELETE, id: "s1", author: "Mriganka" }),
      text("."),
    );
    expect(listSuggestions(d)).toEqual([
      { id: "s1", kind: SUGGESTION_DELETE, author: "Mriganka", at: "", text: "quietly" },
    ]);
  });

  test("merges adjacent runs that share an id", () => {
    const d = doc(
      text("with", { type: SUGGESTION_INSERT, id: "s1" }),
      text("out looking", { type: SUGGESTION_INSERT, id: "s1" }),
    );
    const found = listSuggestions(d);
    expect(found).toHaveLength(1);
    expect(found[0].text).toBe("without looking");
  });

  test("keeps separate ids apart", () => {
    const d = doc(
      text("a", { type: SUGGESTION_INSERT, id: "s1" }),
      text("b", { type: SUGGESTION_INSERT, id: "s2" }),
    );
    expect(listSuggestions(d).map((s) => s.id)).toEqual(["s1", "s2"]);
  });
});

describe("resolving one suggestion", () => {
  const inserted = doc(
    text("She left "),
    text("without looking back", { type: SUGGESTION_INSERT, id: "s1" }),
    text("."),
  );
  const deleted = doc(
    text("She left "),
    text("quietly ", { type: SUGGESTION_DELETE, id: "s1" }),
    text("by the pier."),
  );

  test("accepting an insertion keeps the words as ordinary prose", () => {
    const out = acceptSuggestion(inserted, "s1");
    expect(flatten(out)).toBe("She left without looking back.");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("rejecting an insertion removes the words", () => {
    const out = rejectSuggestion(inserted, "s1");
    expect(flatten(out)).toBe("She left .");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("accepting a deletion removes the words", () => {
    const out = acceptSuggestion(deleted, "s1");
    expect(flatten(out)).toBe("She left by the pier.");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("rejecting a deletion puts the words back as prose", () => {
    const out = rejectSuggestion(deleted, "s1");
    expect(flatten(out)).toBe("She left quietly by the pier.");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("leaves other suggestions untouched", () => {
    const d = doc(
      text("a", { type: SUGGESTION_INSERT, id: "s1" }),
      text("b", { type: SUGGESTION_INSERT, id: "s2" }),
    );
    const out = acceptSuggestion(d, "s1");
    expect(listSuggestions(out).map((s) => s.id)).toEqual(["s2"]);
    expect(flatten(out)).toBe("ab");
  });
});

describe("formatting and structure survive", () => {
  test("accepting keeps the author's other marks", () => {
    const d = doc({
      type: "text",
      text: "certain",
      marks: [
        { type: "bold" },
        { type: SUGGESTION_INSERT, attrs: { id: "s1", author: "A", at: "" } },
      ],
    });
    const out = acceptSuggestion(d, "s1") as unknown as {
      content: { content: { marks: { type: string }[] }[] }[];
    };
    expect(out.content[0].content[0].marks).toEqual([{ type: "bold" }]);
  });

  test("a paragraph emptied by a rejection stays a paragraph", () => {
    const d = doc(text("all of it", { type: SUGGESTION_INSERT, id: "s1" }));
    const out = rejectSuggestion(d, "s1") as unknown as {
      content: { type: string; content: unknown[] }[];
    };
    expect(out.content).toHaveLength(1);
    expect(out.content[0].type).toBe("paragraph");
    expect(out.content[0].content).toEqual([]);
  });
});

describe("bulk resolution", () => {
  const mixed = doc(
    text("New. ", { type: SUGGESTION_INSERT, id: "s1" }),
    text("Kept. "),
    text("Doomed.", { type: SUGGESTION_DELETE, id: "s2" }),
  );

  test("accept all takes every proposal", () => {
    const out = acceptAllSuggestions(mixed);
    expect(flatten(out)).toBe("New. Kept. ");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("reject all restores the manuscript", () => {
    const out = rejectAllSuggestions(mixed);
    expect(flatten(out)).toBe("Kept. Doomed.");
    expect(hasSuggestions(out)).toBe(false);
  });

  test("acceptedDoc matches the reject-all view the agents read", () => {
    expect(flatten(acceptedDoc(mixed))).toBe(flatten(rejectAllSuggestions(mixed)));
  });
});

test("suggestion ids are unique", () => {
  const ids = new Set(Array.from({ length: 50 }, newSuggestionId));
  expect(ids.size).toBe(50);
});
