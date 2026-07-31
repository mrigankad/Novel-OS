// Theme bootstrap runs at import time (before React renders) to avoid a flash.

export type Theme = "light" | "dark";

const KEY = "novel-os-theme";

export function getTheme(): Theme {
  const saved = localStorage.getItem(KEY) as Theme | null;
  if (saved === "light" || saved === "dark") return saved;
  // matchMedia is absent in some test environments (jsdom)
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  return prefersDark ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "dark" ? "#0e1320" : "#f3ecdd");
}

export function setTheme(theme: Theme): void {
  localStorage.setItem(KEY, theme);
  applyTheme(theme);
}

// --- Reader font (manuscript canvas only; chrome always stays on --font-sans) ---

export type ReaderFont = "sans" | "serif" | "mono";

export const READER_FONTS: { value: ReaderFont; label: string }[] = [
  { value: "sans", label: "Google Sans" },
  { value: "serif", label: "Newsreader" },
  { value: "mono", label: "Google Sans Code" },
];

const FONT_KEY = "novel-os-reader-font";

export function getReaderFont(): ReaderFont {
  const saved = localStorage.getItem(FONT_KEY) as ReaderFont | null;
  return saved === "serif" || saved === "mono" || saved === "sans" ? saved : "sans";
}

export function applyReaderFont(font: ReaderFont): void {
  document.documentElement.dataset.readerFont = font;
}

export function setReaderFont(font: ReaderFont): void {
  localStorage.setItem(FONT_KEY, font);
  applyReaderFont(font);
}

// Apply immediately on first import.
applyTheme(getTheme());
applyReaderFont(getReaderFont());
