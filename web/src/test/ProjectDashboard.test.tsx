import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ProjectDashboard from "../routes/ProjectDashboard";
import * as client from "../api/client";
import { TestProviders } from "./TestProviders";

test("shows project title and chapter cards", async () => {
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena", pipeline_step: "drafted" },
  ]);
  vi.spyOn(client.api, "characters").mockResolvedValue([]);
  vi.spyOn(client.api, "plotThreads").mockResolvedValue([]);
  render(
    <TestProviders>
      <MemoryRouter initialEntries={["/projects/p"]}>
        <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
      </MemoryRouter>
    </TestProviders>,
  );
  expect(await screen.findByText("My Novel")).toBeInTheDocument();
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(screen.getByLabelText("Draft")).toBeInTheDocument();
});
