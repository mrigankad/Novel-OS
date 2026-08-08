import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import SuggestionsPanel from "../components/SuggestionsPanel";
import { SUGGESTION_DELETE, SUGGESTION_INSERT, listSuggestions } from "../lib/trackChanges";
import type { PMDoc } from "../lib/richText";

function suggested(t: string, type: string, id: string) {
  return {
    type: "text",
    text: t,
    marks: [{ type, attrs: { id, author: "Mriganka", at: "" } }],
  };
}

const docWithBoth = {
  type: "doc",
  content: [
    {
      type: "paragraph",
      content: [
        suggested("without looking back", SUGGESTION_INSERT, "s1"),
        { type: "text", text: " She left " },
        suggested("quietly", SUGGESTION_DELETE, "s2"),
      ],
    },
  ],
} as PMDoc;

test("renders nothing when there is nothing to review", () => {
  const { container } = render(
    <SuggestionsPanel
      doc={{ type: "doc", content: [{ type: "paragraph" }] } as PMDoc}
      onChange={() => {}}
    />,
  );
  expect(container).toBeEmptyDOMElement();
});

test("lists each pending change with its kind and author", () => {
  render(<SuggestionsPanel doc={docWithBoth} onChange={() => {}} />);
  expect(screen.getByText("2 pending changes")).toBeInTheDocument();
  expect(screen.getByText("Insert")).toBeInTheDocument();
  expect(screen.getByText("Delete")).toBeInTheDocument();
  expect(screen.getByText("without looking back")).toBeInTheDocument();
  expect(screen.getAllByText("Mriganka")).toHaveLength(2);
});

test("accepting one change resolves only that change", async () => {
  const onChange = vi.fn();
  render(<SuggestionsPanel doc={docWithBoth} onChange={onChange} />);

  await userEvent.click(screen.getByRole("button", { name: "Accept insertion" }));

  const next = onChange.mock.calls[0][0] as PMDoc;
  const left = listSuggestions(next);
  expect(left).toHaveLength(1);
  expect(left[0].id).toBe("s2");
});

test("reject all restores the manuscript in one step", async () => {
  const onChange = vi.fn();
  render(<SuggestionsPanel doc={docWithBoth} onChange={onChange} />);

  await userEvent.click(screen.getByRole("button", { name: "Reject all" }));

  const next = onChange.mock.calls[0][0] as PMDoc;
  expect(listSuggestions(next)).toEqual([]);
  // The rejected insertion is gone; the text saved from deletion is still here.
  const flat = JSON.stringify(next);
  expect(flat).not.toContain("without looking back");
  expect(flat).toContain("quietly");
});
