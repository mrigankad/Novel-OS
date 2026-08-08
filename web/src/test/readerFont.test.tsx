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

test("defaults the manuscript canvas to SF Pro", () => {
  renderEditor();
  expect(getReaderFont()).toBe("sans");
  const group = screen.getByRole("radiogroup", { name: "Reading font" });
  expect(group.querySelector('[aria-checked="true"]')).toHaveAttribute("aria-label", "SF Pro");
});

test("switching the reader font rebinds the token and persists it", async () => {
  const user = userEvent.setup();
  renderEditor();
  await user.click(screen.getByRole("radio", { name: "Newsreader" }));

  expect(document.documentElement.dataset.readerFont).toBe("serif");
  expect(getReaderFont()).toBe("serif");
});

test("offers all three reader fonts as visible choices", () => {
  renderEditor();
  const group = screen.getByRole("radiogroup", { name: "Reading font" });
  const labels = [...group.querySelectorAll('[role="radio"]')].map((el) =>
    el.getAttribute("aria-label"),
  );
  expect(labels).toEqual(["SF Pro", "Newsreader", "Mono"]);
});
