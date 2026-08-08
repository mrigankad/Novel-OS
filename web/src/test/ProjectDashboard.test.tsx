import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ProjectDashboard from "../routes/ProjectDashboard";
import * as client from "../api/client";

test("shows project title and chapter cards", async () => {
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena" },
  ]);
  vi.spyOn(client.api, "binder").mockResolvedValue([
    {
      id: "part-manuscript", type: "part", title: "Manuscript",
      children: [{
        id: "ch-001", type: "chapter", title: "Opening", chapter_number: 1,
        synopsis: "Lena opens the pier.", status: "drafted", pov: "Lena",
        word_count: 2300, parent_id: "part-manuscript", children: [],
      }],
    },
  ]);
  vi.spyOn(client.api, "codex").mockResolvedValue([]);
  vi.spyOn(client.api, "relationships").mockResolvedValue([]);
  vi.spyOn(client.api, "continuity").mockResolvedValue({ findings: [], summary: "" } as never);
  render(
    <MemoryRouter initialEntries={["/projects/p"]}>
      <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("My Novel")).toBeInTheDocument();
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(screen.getByText(/drafted/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/Add a synopsis/i)).toBeInTheDocument();
});
