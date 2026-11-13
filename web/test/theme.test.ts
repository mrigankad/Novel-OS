import { afterEach, describe, expect, it, vi } from "vitest";
import { getThemeChoice, resolveTheme, setThemeChoice, subscribeTheme, THEME_KEY } from "@/lib/theme";

function mockMatchMedia(dark: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: dark && query.includes("dark"), media: query, onchange: null,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("theme store", () => {
  it("defaults to system, and system resolves to dark when the OS prefers dark", () => {
    mockMatchMedia(true);
    expect(getThemeChoice()).toBe("system");
    expect(resolveTheme()).toBe("dark");
    mockMatchMedia(false);
    expect(resolveTheme()).toBe("light");
  });

  it("persists an explicit choice and applies it to <html>", () => {
    mockMatchMedia(true);
    const cb = vi.fn();
    const off = subscribeTheme(cb);
    setThemeChoice("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(getThemeChoice()).toBe("light");
    expect(resolveTheme()).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(cb).toHaveBeenCalled();
    off();
  });

  it("going back to system clears storage and the attribute", () => {
    mockMatchMedia(false);
    setThemeChoice("dark");
    setThemeChoice("system");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});
