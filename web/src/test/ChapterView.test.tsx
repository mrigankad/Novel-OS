import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { useEffect } from "react";
import { vi } from "vitest";

// TipTap needs a real DOM layout; stub the rich-text surface for route tests.
vi.mock("../components/RichTextEditor", () => ({
  // Named with a capital so the hooks lint rule recognises it as a component.
  default: function MockRichTextEditor(props: {
    doc: { type: string; content?: unknown[] };
    onChange: (d: unknown) => void;
    onReady?: (h: {
      getText: () => string;
      getJSON: () => unknown;
      getSelection: () => null;
      focus: () => void;
      editor: null;
    }) => void;
  }) {
    const text =
      // best-effort flatten for the textarea fixture
      JSON.stringify(props.doc).includes("Revised")
        ? "Revised prose"
        : "";
    // Mirror the real editor: hand the parent its handle from an effect, never
    // during render, or FinalEditor's setState lands mid-render.
    const { onReady, doc } = props;
    useEffect(() => {
      onReady?.({
        getText: () => text,
        getJSON: () => doc,
        getSelection: () => null,
        focus: () => {},
        editor: null,
      });
    }, [onReady, doc, text]);
    return (
      <textarea
        aria-label="Final manuscript"
        value={text}
        onChange={(e) =>
          props.onChange({
            type: "doc",
            content: [{ type: "paragraph", content: [{ type: "text", text: e.target.value }] }],
          })
        }
      />
    );
  },
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
  expect(await screen.findByText("Outline")).toBeInTheDocument();
  expect(screen.getByText("Final")).toBeInTheDocument();
  expect(await screen.findByText("Beats")).toBeInTheDocument();
});

test("Final pane auto-seeds from revised and saves edits", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue(META);
  vi.spyOn(client.api, "chapters").mockResolvedValue([]);
  let hasFinal = false;
  vi.spyOn(client.api, "stages").mockImplementation(async () => ({
    number: 1, status: "edited",
    outline: "# Beats", draft: "d", revised: "Revised prose",
    final: hasFinal ? "Revised prose" : null,
    continuity: null,
  }));
  const promote = vi
    .spyOn(client.api, "promoteFinal")
    .mockImplementation(async () => {
      hasFinal = true;
      return { final: "Revised prose", word_count: 2 };
    });
  const getFinalDoc = vi.spyOn(client.api, "getFinalDoc").mockResolvedValue({
    doc: {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: "Revised prose" }] }],
    },
    markdown: "Revised prose\n",
    word_count: 2,
  });
  const saveFinalDoc = vi.spyOn(client.api, "saveFinalDoc").mockResolvedValue({
    doc: {
      type: "doc",
      content: [{ type: "paragraph", content: [{ type: "text", text: "Revised prose edited" }] }],
    },
    markdown: "Revised prose edited\n",
    word_count: 3,
  });
  vi.spyOn(client.api, "comments").mockResolvedValue([]);
  vi.spyOn(client.api, "snapshots").mockResolvedValue([]);

  const user = userEvent.setup();
  renderAt();

  // Opening the chapter seeds Final so the manuscript is editable.
  await screen.findByLabelText("Final manuscript");
  expect(promote).toHaveBeenCalled();
  expect(getFinalDoc).toHaveBeenCalled();

  const editor = await screen.findByDisplayValue("Revised prose");
  await user.type(editor, " edited");
  await user.click(screen.getByRole("button", { name: /^Save$/i }));
  expect(saveFinalDoc).toHaveBeenCalled();
});
