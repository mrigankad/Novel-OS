import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import ModeSwitch from "../components/ModeSwitch";
import {
  chapterLayoutFor,
  getStudioMode,
  setStudioMode,
} from "../lib/studioMode";

beforeEach(() => {
  localStorage.clear();
});

test("Write is the default, because that is what the app is for", () => {
  expect(getStudioMode()).toBe("write");
});

test("an unrecognised stored value falls back rather than breaking the layout", () => {
  localStorage.setItem("novelos-studio-mode", "nonsense");
  expect(getStudioMode()).toBe("write");
});

test("the chosen mode persists", () => {
  setStudioMode("revise");
  expect(getStudioMode()).toBe("revise");
});

test("Write clears both rails so the manuscript is the page", () => {
  const layout = chapterLayoutFor("write");
  expect(layout.binder).toBe(false);
  expect(layout.inspector).toBe(false);
});

test("Revise opens the Inspector on continuity", () => {
  const layout = chapterLayoutFor("revise");
  expect(layout.inspector).toBe(true);
  expect(layout.inspectorTab).toBe("continuity");
});

test("Plan shows structure without the notes rail", () => {
  const layout = chapterLayoutFor("plan");
  expect(layout.binder).toBe(true);
  expect(layout.inspector).toBe(false);
});

test("the switch marks the active mode for assistive tech", async () => {
  render(<ModeSwitch />);
  const write = screen.getByRole("radio", { name: "Write" });
  expect(write).toHaveAttribute("aria-checked", "true");

  await userEvent.click(screen.getByRole("radio", { name: "Plan" }));

  expect(screen.getByRole("radio", { name: "Plan" })).toHaveAttribute(
    "aria-checked", "true",
  );
  expect(getStudioMode()).toBe("plan");
});

test("two mounted switches stay in step", async () => {
  render(
    <>
      <div data-testid="a"><ModeSwitch /></div>
      <div data-testid="b"><ModeSwitch /></div>
    </>,
  );

  const inA = screen.getByTestId("a");
  await userEvent.click(
    screen.getAllByRole("radio", { name: "Revise" })[0],
  );

  // Both switchers reflect the change, without a shared provider.
  for (const el of screen.getAllByRole("radio", { name: "Revise" })) {
    expect(el).toHaveAttribute("aria-checked", "true");
  }
  expect(inA).toBeInTheDocument();
});

test("cmd+2 selects Write", async () => {
  setStudioMode("plan");
  render(<ModeSwitch />);

  await userEvent.keyboard("{Meta>}2{/Meta}");

  expect(getStudioMode()).toBe("write");
});
