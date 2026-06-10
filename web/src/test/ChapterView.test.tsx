import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ChapterView from "../routes/ChapterView";
import * as client from "../api/client";

test("renders outline and draft, with a fallback when missing", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue({
    number: 1, title: "Opening", status: "drafted", word_count: 5, pov: "Lena",
    outline: "# Beats", draft: null,
  });
  render(
    <MemoryRouter initialEntries={["/projects/p/chapters/1"]}>
      <Routes><Route path="/projects/:id/chapters/:n" element={<ChapterView />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("Beats")).toBeInTheDocument();
  expect(screen.getByText(/not generated yet/i)).toBeInTheDocument();
});
