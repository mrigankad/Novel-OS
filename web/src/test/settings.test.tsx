import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import Settings from "../routes/Settings";
import * as client from "../api/client";
import { ToastProvider } from "../components/Toaster";

test("Connections renders, detects models and offers the Claude Code command", async () => {
  vi.spyOn(client.api, "studioLlm").mockResolvedValue({
    configured: true, provider: "ollama_cloud", model: "gpt-oss:120b", preset: "ollama_cloud",
    mature_capable: false, error: null, onboarding_completed: true,
    presets: [{ id: "ollama_cloud", label: "Ollama Cloud", hint: "h", provider: "ollama_cloud", model: "gpt-oss:120b", mature_capable: false }],
  } as never);
  const models = vi.spyOn(client.api, "studioModels").mockResolvedValue({
    ok: true, provider: "ollama_cloud", endpoint: "x", error: null,
    models: [{ id: "gpt-oss:120b" }, { id: "qwen3-coder:480b" }],
  });
  render(<ToastProvider><Settings /></ToastProvider>);
  expect(await screen.findByRole("option", { name: /qwen3-coder/ })).toBeInTheDocument();
  expect(models).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/claude mcp add novel-os/)).toBeInTheDocument();
});
