import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import Shell from "../Shell";
import * as client from "../api/client";
import { MemoryRouter } from "./testRouter";

test("renders the studio shell with the wordmark", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([]);
  render(<MemoryRouter><Shell><p>page</p></Shell></MemoryRouter>);
  expect(screen.getByRole("img", { name: /Novel OS/i })).toBeInTheDocument();
  expect(screen.getByText("page")).toBeInTheDocument();
});
