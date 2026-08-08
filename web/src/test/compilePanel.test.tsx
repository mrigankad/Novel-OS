import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import CompilePanel from "../components/CompilePanel";
import { ToastProvider } from "../components/Toaster";
import { api, type StyleSheet } from "../api/client";

function style(over: Partial<StyleSheet["styles"][string]> = {}) {
  return {
    font: "serif", size_pt: 12, line_height: 1.6, align: "left",
    bold: false, italic: false, small_caps: false,
    first_line_indent_em: 1.5, space_before_em: 0, space_after_em: 0,
    page_break_before: false,
    ...over,
  };
}

const SHEET: StyleSheet = {
  scene_break_marker: "* * *",
  styles: {
    title: style(),
    subtitle: style(),
    chapter_title: style({ size_pt: 18, align: "center", bold: true }),
    body: style(),
    first_paragraph: style({ first_line_indent_em: 0 }),
    block_quote: style({ size_pt: 11.5, italic: true }),
    scene_break: style({ align: "center" }),
  },
};

function renderPanel() {
  return render(
    <ToastProvider>
      <CompilePanel projectId="book" />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "styles").mockResolvedValue(structuredClone(SHEET));
});

test("shows only the styles a writer actually changes", async () => {
  renderPanel();
  expect(await screen.findByText("Chapter title")).toBeInTheDocument();
  expect(screen.getByText("Body")).toBeInTheDocument();
  expect(screen.getByText("Block quote")).toBeInTheDocument();
  // The full sheet has seven roles; a panel of all of them is a settings screen.
  expect(screen.queryByText("First paragraph")).not.toBeInTheDocument();
});

test("the compile link carries the chosen format", async () => {
  renderPanel();
  const link = await screen.findByRole("link", { name: /Compile/ });
  expect(link).toHaveAttribute("href", expect.stringContaining("format=html"));
});

test("editing a size and saving sends the whole sheet", async () => {
  const save = vi.spyOn(api, "saveStyles").mockResolvedValue(structuredClone(SHEET));
  renderPanel();

  const size = await screen.findByLabelText("Body size in points");
  await userEvent.clear(size);
  await userEvent.type(size, "13");
  await userEvent.click(screen.getByRole("button", { name: "Save styles" }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  const sent = save.mock.calls[0][1];
  expect(sent.styles.body.size_pt).toBe(13);
  // Untouched roles travel unchanged - the API validates the sheet whole.
  expect(sent.styles.chapter_title.size_pt).toBe(18);
});

test("the scene break marker is editable", async () => {
  const save = vi.spyOn(api, "saveStyles").mockResolvedValue(structuredClone(SHEET));
  renderPanel();

  const marker = await screen.findByLabelText("Scene break marker");
  await userEvent.clear(marker);
  await userEvent.type(marker, "~~~");
  await userEvent.click(screen.getByRole("button", { name: "Save styles" }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  expect(save.mock.calls[0][1].scene_break_marker).toBe("~~~");
});

test("a rejected sheet surfaces the reason and keeps the panel open", async () => {
  vi.spyOn(api, "saveStyles").mockRejectedValue(
    new Error("body: size must be between 4 and 96 points."),
  );
  renderPanel();

  await userEvent.click(await screen.findByRole("button", { name: "Save styles" }));

  expect(await screen.findByText(/size must be between 4 and 96/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save styles" })).toBeInTheDocument();
});

test("renders nothing if the stylesheet cannot be loaded", async () => {
  vi.spyOn(api, "styles").mockRejectedValue(new Error("offline"));
  renderPanel();
  // Nothing to offer without a sheet - and no error box either, because a
  // failed background fetch is not something the writer asked for.
  await waitFor(() =>
    expect(screen.queryByRole("region", { name: "Compile" })).not.toBeInTheDocument(),
  );
  expect(screen.queryByRole("button", { name: "Save styles" })).not.toBeInTheDocument();
});
