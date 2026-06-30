import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import ProjectsList from "../routes/ProjectsList";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

test("renders project cards from the API", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([
    { id: "the-last-signal", title: "The Last Signal", genre: "Sci-Fi", chapter_count: 3, status: "in_progress" },
  ]);
  render(
    <TestProviders>
      <MemoryRouter><ProjectsList /></MemoryRouter>
    </TestProviders>,
  );
  expect(await screen.findByText("The Last Signal")).toBeInTheDocument();
  expect(screen.getByText(/3 chapters/i)).toBeInTheDocument();
});
