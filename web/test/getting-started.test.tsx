import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { GettingStarted } from "@/components/getting-started";
import type { Project } from "@/lib/api";

vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a> }));

const book = { id: "b1", title: "Orchard", word_count: 0, chapter_count: 0 } as Project;

function setup(connections: unknown[], projects: Project[]) {
  global.fetch = vi.fn(async () => new Response(JSON.stringify({ connections, detected: [] }),
    { headers: { "content-type": "application/json" } })) as typeof fetch;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><GettingStarted projects={projects} /></QueryClientProvider>);
}

beforeEach(() => localStorage.clear());

test("shows remaining steps and ticks off what's done", async () => {
  setup([{ id: "c", provider: "ollama_cloud", label: "Ollama Cloud", is_default: true }], [book]);
  expect(await screen.findByText(/Getting started · 2 of 3/)).toBeInTheDocument();
  expect(screen.getByText("Writing with Ollama Cloud.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Agent room/ })).toHaveAttribute("href", "/p/b1/room");
});

test("hides when every required step is done, and stays hidden once dismissed", async () => {
  const { unmount } = setup([], []);
  await userEvent.click(await screen.findByRole("button", { name: /Dismiss/ }));
  expect(screen.queryByText(/Getting started/)).not.toBeInTheDocument();
  unmount();
  setup([], []);
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByText(/Getting started/)).not.toBeInTheDocument();
});
