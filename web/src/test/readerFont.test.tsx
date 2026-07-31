import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

vi.mock("../components/MarkdownEditor", () => ({
  default: (props: { value: string; onChange: (v: string) => void }) => (
    <textarea value={props.value} onChange={(e) => props.onChange(e.target.value)} />
  ),
}));

import FinalEditor from "../components/FinalEditor";
import { getReaderFont } from "../theme";

function renderEditor() {
  render(
    <FinalEditor
      hasFinal
      canPromote={false}
      promoteFrom=""
      text="Once upon a time."
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

test("defaults the manuscript canvas to Google Sans", () => {
  renderEditor();
  expect(getReaderFont()).toBe("sans");
  expect(screen.getByLabelText("Reading font")).toHaveValue("sans");
});

test("switching the reader font rebinds the token and persists it", async () => {
  renderEditor();
  await userEvent.selectOptions(screen.getByLabelText("Reading font"), "serif");

  // Applied to <html>, which is what rebinds --font-prose in index.css.
  expect(document.documentElement.dataset.readerFont).toBe("serif");
  // Persisted, so it survives a reload.
  expect(getReaderFont()).toBe("serif");
});

test("offers all three reader fonts", () => {
  renderEditor();
  const labels = Array.from(
    screen.getByLabelText("Reading font").querySelectorAll("option"),
  ).map((o) => o.textContent);
  expect(labels).toEqual(["Google Sans", "Newsreader", "Google Sans Code"]);
});
