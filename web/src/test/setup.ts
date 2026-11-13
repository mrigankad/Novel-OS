import "@testing-library/jest-dom";
import { createElement } from "react";
import { vi } from "vitest";

// next/link needs a mounted App Router; tests render a plain anchor instead.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: Record<string, unknown>) => {
    delete rest.replace;
    delete rest.prefetch;
    return createElement("a", { href, ...rest }, children as never);
  },
}));

// jsdom lacks matchMedia; ChapterView uses it for compact binder/notes.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
