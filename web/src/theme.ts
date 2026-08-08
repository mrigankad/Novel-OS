// Light-only instrument theme. Dark mode removed (2026-08-03 monochrome UI).

export type Theme = "light";

export function getTheme(): Theme {
  return "light";
}

// The theme argument is accepted and ignored: dark mode was removed in the
// 2026-08-03 monochrome UI, but callers still pass a value.
export function applyTheme(): void {
  const root = document.documentElement;
  root.dataset.theme = "light";
  root.style.colorScheme = "light";
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", "#1676df");
}

export function setTheme(): void {
  applyTheme();
}

// --- Reader font (manuscript canvas only; chrome always stays on --font-sans) ---

export type ReaderFont = "sans" | "serif" | "mono";

export const READER_FONTS: { value: ReaderFont; label: string }[] = [
  { value: "sans", label: "SF Pro" },
  { value: "serif", label: "Newsreader" },
  { value: "mono", label: "Mono" },
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

applyTheme();
applyReaderFont(getReaderFont());
