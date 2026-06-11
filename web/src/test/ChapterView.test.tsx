import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";

// CodeMirror doesn't render meaningfully in jsdom — swap it for a plain textarea.
vi.mock("../components/MarkdownEditor", () => ({
  default: (props: { value: string; onChange: (v: string) => void }) => (
    <textarea value={props.value} onChange={(e) => props.onChange(e.target.value)} />
  ),
}));

import ChapterView from "../routes/ChapterView";
import * as client from "../api/client";

function renderAt(path = "/projects/p/chapters/1") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
      </Routes>
    </MemoryRouter>,
  );
}

const META = {
  number: 1, title: "Opening", status: "drafted", word_count: 5, pov: "Lena",
  outline: null, draft: null,
};

test("shows the pipeline flow and renders the selected stage", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue(META);
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1, status: "drafted",
    outline: "# Beats", draft: null, revised: null, final: null, continuity: null,
  });

  renderAt();
  // flow ribbon shows every stage
  expect(await screen.findByText("Outline")).toBeInTheDocument();
  expect(screen.getByText("Final")).toBeInTheDocument();
  // outline is the only present stage, so it renders by default
  expect(await screen.findByText("Beats")).toBeInTheDocument();
});

test("Final pane offers to promote when no final exists, and saves edits", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue(META);
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  vi.spyOn(client.api, "stages").mockResolvedValue({
    number: 1, status: "edited",
    outline: "# Beats", draft: "d", revised: "Revised prose", final: null, continuity: null,
  });
  const promote = vi
    .spyOn(client.api, "promoteFinal")
    .mockResolvedValue({ final: "Revised prose", word_count: 2 });
  const saveFinal = vi
    .spyOn(client.api, "saveFinal")
    .mockResolvedValue({ final: "Revised prose edited", word_count: 3 });

  const user = userEvent.setup();
  renderAt();

  // open the Final stage
  await user.click(await screen.findByText("Final"));
  const promoteBtn = await screen.findByRole("button", { name: /Promote Revised → Final/i });
  await user.click(promoteBtn);
  expect(promote).toHaveBeenCalledWith("p", 1);

  // editor now shows the promoted text; edit + save
  const editor = await screen.findByDisplayValue("Revised prose");
  await user.type(editor, " edited");
  await user.click(screen.getByRole("button", { name: /^Save$/i }));
  expect(saveFinal).toHaveBeenCalled();
});
