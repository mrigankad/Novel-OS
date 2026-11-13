import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Select } from "@/components/ui/select";

const OPTIONS = [
  { value: "ollama", label: "Ollama Cloud", hint: "gpt-oss:120b" },
  { value: "claude", label: "Claude Code login" },
  { value: "azure", label: "Azure OpenAI", disabled: true },
  { value: "openai", label: "OpenAI" },
];

function Harness({ onPick }: { onPick?: (v: string) => void }) {
  const [v, setV] = useState<string>("claude");
  return <Select aria-label="Connection" value={v} options={OPTIONS}
    onChange={(x) => { setV(x); onPick?.(x); }} />;
}

test("shows the selected label and opens a listbox with the selection marked", async () => {
  render(<Harness />);
  const button = screen.getByRole("button", { name: "Connection" });
  expect(button).toHaveTextContent("Claude Code login");
  await userEvent.click(button);
  expect(screen.getByRole("listbox")).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /Claude Code login/ })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("gpt-oss:120b")).toBeInTheDocument();
});

test("keyboard: arrows skip disabled options, Enter picks, focus returns", async () => {
  const picked: string[] = [];
  render(<Harness onPick={(v) => picked.push(v)} />);
  const button = screen.getByRole("button", { name: "Connection" });
  button.focus();
  await userEvent.keyboard("{ArrowDown}");  // open on Claude
  await userEvent.keyboard("{ArrowDown}");  // Azure is disabled -> OpenAI
  await userEvent.keyboard("{Enter}");
  expect(picked).toEqual(["openai"]);
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  expect(button).toHaveFocus();
  expect(button).toHaveTextContent("OpenAI");
});

test("type-ahead jumps to a match and Escape closes without choosing", async () => {
  const picked: string[] = [];
  render(<Harness onPick={(v) => picked.push(v)} />);
  const button = screen.getByRole("button", { name: "Connection" });
  button.focus();
  await userEvent.keyboard("{ArrowDown}o");
  expect(screen.getByRole("button", { name: "Connection" })).toHaveAttribute(
    "aria-activedescendant", expect.stringContaining("o0"));
  await userEvent.keyboard("{Escape}");
  expect(picked).toEqual([]);
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

test("clicking outside closes the menu", async () => {
  render(<><Harness /><p>outside</p></>);
  await userEvent.click(screen.getByRole("button", { name: "Connection" }));
  await userEvent.click(screen.getByText("outside"));
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});
