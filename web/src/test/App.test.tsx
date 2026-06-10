import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "../App";
import * as client from "../api/client";

test("renders the app shell with the wordmark", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByText(/Novel OS/i)).toBeInTheDocument();
});
