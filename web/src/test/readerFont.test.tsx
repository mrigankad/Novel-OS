import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("../components/RichTextEditor", () => ({
  default: () => <div aria-label="Final manuscript" />,
}));

vi.mock("../components/ContinueChat", () => ({
  default: () => null,
}));

import FinalEditor from "../components/FinalEditor";
import { getReaderFont } from "../theme";
import { EMPTY_DOC } from "../lib/richText";

function renderEditor() {
  render(
    <FinalEditor
      projectId="book"
      chapterNumber={1}
      hasFinal
      canPromote={false}
      promoteFrom=""
      doc={EMPTY_DOC}
      wordCount={4}
      onChange={() => {}}
      onSave={() => {}}
      onPromote={() => {}}
      dirty={false}
      busy={null}
      lastSaved={null}
      focus={false}
      onToggleFocus={() => {}}
    />,
  );
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.readerFont;
});

test("defaults the manuscript canvas to Newsreader", () => {
  renderEditor();
  expect(getReaderFont()).toBe("serif");
  const group = screen.getByRole("radiogroup", { name: "Reading font" });
  expect(group.querySelector('[aria-checked="true"]')).toHaveAttribute("aria-label", "Newsreader");
});

test("switching the reader font rebinds the token and persists it", async () => {
  const user = userEvent.setup();
  renderEditor();
  await user.click(screen.getByRole("radio", { name: "Inter Tight" }));

  expect(document.documentElement.dataset.readerFont).toBe("sans");
  expect(getReaderFont()).toBe("sans");
});

test("offers both reader fonts as visible choices", () => {
  renderEditor();
  const group = screen.getByRole("radiogroup", { name: "Reading font" });
  const labels = [...group.querySelectorAll('[role="radio"]')].map((el) =>
    el.getAttribute("aria-label"),
  );
  expect(labels).toEqual(["Newsreader", "Inter Tight"]);
});
