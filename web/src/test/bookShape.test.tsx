import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import BookShape from "../components/BookShape";
import { api, type BookShapeReport } from "../api/client";

function chapter(number: number, movement: number, written = true) {
  return {
    number,
    title: `Ch ${number}`,
    pov: "Lena",
    written,
    plot_advances: movement,
    character_development: 0,
    emotional_beats: 0,
    new_information: 0,
    threads_touched: 0,
    word_count: 2500,
    movement,
    flat: written && movement === 0,
  };
}

const REPORT: BookShapeReport = {
  chapters: [chapter(1, 4), chapter(2, 0), chapter(3, 0), chapter(4, 0), chapter(5, 3)],
  stalls: [{
    start: 2,
    end: 4,
    reason: "Lena carries 3 chapters in a row without advancing a thread or changing - the protagonist has gone reactive",
    chapters: [2, 3, 4],
    length: 3,
  }],
};

function renderShape() {
  return render(
    <MemoryRouter>
      <BookShape projectId="book" />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(api, "bookShape").mockResolvedValue(REPORT);
});

test("draws one bar per chapter, each linking to it", async () => {
  renderShape();
  const strip = await screen.findByRole("list", { name: "Chapters" });
  const bars = within(strip).getAllByRole("listitem");
  expect(bars).toHaveLength(5);
  expect(bars[0]).toHaveAttribute("href", "/projects/book/chapters/1");
});

test("each bar describes itself for screen readers", async () => {
  renderShape();
  expect(await screen.findByLabelText(/Chapter 1: Ch 1 — 4 changes/)).toBeInTheDocument();
});

test("a stalled chapter says so in its label, not only in colour", async () => {
  renderShape();
  expect(
    await screen.findByLabelText(/Chapter 3.*part of a stalled run/),
  ).toBeInTheDocument();
});

test("an unwritten chapter is called out rather than shown as flat", async () => {
  vi.spyOn(api, "bookShape").mockResolvedValue({
    chapters: [chapter(1, 3), chapter(2, 0, false)],
    stalls: [],
  });
  renderShape();
  expect(await screen.findByLabelText(/Chapter 2.*not written yet/)).toBeInTheDocument();
});

test("the sagging run is named in plain language", async () => {
  renderShape();
  expect(await screen.findByText(/the protagonist has gone reactive/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ch 2–4" })).toBeInTheDocument();
});

test("a healthy book shows bars and no warnings", async () => {
  vi.spyOn(api, "bookShape").mockResolvedValue({
    chapters: [chapter(1, 3), chapter(2, 4)],
    stalls: [],
  });
  renderShape();
  await screen.findByRole("list", { name: "Chapters" });
  expect(screen.queryByRole("list", { name: "Stalled stretches" })).not.toBeInTheDocument();
});

test("renders nothing for a project with no chapters", async () => {
  vi.spyOn(api, "bookShape").mockResolvedValue({ chapters: [], stalls: [] });
  const { container } = renderShape();
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});

test("a failed lookup stays silent", async () => {
  vi.spyOn(api, "bookShape").mockRejectedValue(new Error("offline"));
  const { container } = renderShape();
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
