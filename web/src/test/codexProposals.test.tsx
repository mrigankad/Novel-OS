import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import CodexProposals from "../components/CodexProposals";
import { api } from "../api/client";

const PROPOSALS = [
  {
    name: "Mara",
    entry_type: "character" as const,
    mentions: 12,
    evidence: "12 mentions, speaks",
    chapters: [1, 2],
    excerpt: "You should go inside, said Mara.",
  },
  {
    name: "Grey Harbour",
    entry_type: "location" as const,
    mentions: 4,
    evidence: "4 mentions, named place",
    chapters: [2],
    excerpt: "They reached Grey Harbour before dawn.",
  },
];

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "codexProposals").mockResolvedValue(PROPOSALS);
});

test("lists what was found with the evidence for each", async () => {
  render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  expect(await screen.findByText("Mara")).toBeInTheDocument();
  expect(screen.getByText(/2 names not in your Codex yet/)).toBeInTheDocument();
  expect(screen.getByText(/12 mentions, speaks/)).toBeInTheDocument();
});

test("nothing is written until the writer adds it", async () => {
  const add = vi.spyOn(api, "addCodexEntry").mockResolvedValue([]);
  render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await screen.findByText("Mara");
  expect(add).not.toHaveBeenCalled();
});

test("adding sends the proposal and tells the parent to refresh", async () => {
  const add = vi.spyOn(api, "addCodexEntry").mockResolvedValue([]);
  const onAccepted = vi.fn();
  render(<CodexProposals projectId="book" onAccepted={onAccepted} />);

  await userEvent.click(await screen.findByRole("button", { name: "Add Mara to Codex" }));

  await waitFor(() => expect(add).toHaveBeenCalledWith("book", expect.objectContaining({
    name: "Mara",
    entry_type: "character",
  })));
  expect(onAccepted).toHaveBeenCalled();
});

test("an accepted row leaves the queue without reordering the rest", async () => {
  vi.spyOn(api, "addCodexEntry").mockResolvedValue([]);
  render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await userEvent.click(await screen.findByRole("button", { name: "Add Mara to Codex" }));

  await waitFor(() => expect(screen.queryByText("Mara")).not.toBeInTheDocument());
  expect(screen.getByText("Grey Harbour")).toBeInTheDocument();
});

test("dismissing is as cheap as accepting and writes nothing", async () => {
  const add = vi.spyOn(api, "addCodexEntry").mockResolvedValue([]);
  render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await userEvent.click(await screen.findByRole("button", { name: "Dismiss Mara" }));

  expect(screen.queryByText("Mara")).not.toBeInTheDocument();
  expect(add).not.toHaveBeenCalled();
});

test("dismiss all empties the panel", async () => {
  render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await userEvent.click(await screen.findByRole("button", { name: "Dismiss all" }));

  expect(screen.queryByText("Mara")).not.toBeInTheDocument();
  expect(screen.queryByText("Grey Harbour")).not.toBeInTheDocument();
});

test("renders nothing at all when there is nothing to review", async () => {
  vi.spyOn(api, "codexProposals").mockResolvedValue([]);
  const { container } = render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await waitFor(() => expect(container).toBeEmptyDOMElement());
});

test("a failed lookup stays silent rather than showing an error box", async () => {
  vi.spyOn(api, "codexProposals").mockRejectedValue(new Error("offline"));
  const { container } = render(<CodexProposals projectId="book" onAccepted={() => {}} />);

  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
