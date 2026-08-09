import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import EditCodexModal from "../components/EditCodexModal";
import { ToastProvider } from "../components/Toaster";
import { api, type CodexEntry } from "../api/client";

const PLACE: CodexEntry = {
  id: "loc-001",
  entry_type: "location",
  name: "Grey Harbour",
  summary: "A fogbound port.",
  notes: "Lanterns burn blue.",
};

const PERSON: CodexEntry = {
  id: "char_001",
  entry_type: "character",
  name: "Lena Marrow",
  summary: "",
  notes: "",
  role: "protagonist",
};

function renderModal(entry: CodexEntry = PLACE, onSaved = () => {}) {
  return render(
    <ToastProvider>
      <EditCodexModal
        projectId="book"
        entry={entry}
        open
        onClose={() => {}}
        onSaved={onSaved}
      />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

test("opens pre-filled with the entry as it stands", () => {
  renderModal();
  expect(screen.getByLabelText("Name")).toHaveValue("Grey Harbour");
  expect(screen.getByLabelText("Summary")).toHaveValue("A fogbound port.");
  expect(screen.getByLabelText("Notes")).toHaveValue("Lanterns burn blue.");
});

test("Role is offered for people and hidden for places", () => {
  const { unmount } = renderModal(PLACE);
  expect(screen.queryByLabelText("Role")).not.toBeInTheDocument();
  unmount();

  renderModal(PERSON);
  expect(screen.getByLabelText("Role")).toHaveValue("protagonist");
});

test("sends only the field that changed", async () => {
  const save = vi.spyOn(api, "updateCodexEntry").mockResolvedValue(PLACE);
  renderModal();

  const summary = screen.getByLabelText("Summary");
  await userEvent.clear(summary);
  await userEvent.type(summary, "Quarantined.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(save).toHaveBeenCalled());
  // Crucially: no `notes` key, so the endpoint leaves the notes alone.
  expect(save.mock.calls[0][2]).toEqual({ summary: "Quarantined." });
});

test("saving without changing anything does not call the API", async () => {
  const save = vi.spyOn(api, "updateCodexEntry");
  renderModal();

  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(save).not.toHaveBeenCalled();
});

test("an empty name is refused before it reaches the server", async () => {
  const save = vi.spyOn(api, "updateCodexEntry");
  renderModal();

  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(save).not.toHaveBeenCalled();
  expect(await screen.findByText(/Name cannot be empty/)).toBeInTheDocument();
});

test("a rejected save surfaces the reason and keeps the edits", async () => {
  vi.spyOn(api, "updateCodexEntry").mockRejectedValue(new Error("Name cannot be empty."));
  renderModal();

  await userEvent.type(screen.getByLabelText("Notes"), " More.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText(/Name cannot be empty/)).toBeInTheDocument();
  expect(screen.getByLabelText("Notes")).toHaveValue("Lanterns burn blue. More.");
});

test("a successful save tells the page to reload", async () => {
  vi.spyOn(api, "updateCodexEntry").mockResolvedValue(PLACE);
  const onSaved = vi.fn();
  renderModal(PLACE, onSaved);

  await userEvent.type(screen.getByLabelText("Name"), "!");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => expect(onSaved).toHaveBeenCalled());
});
