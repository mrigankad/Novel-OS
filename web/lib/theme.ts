/** Theme choice store. Framework-free so the root layout can import the boot script. */
export type ThemeChoice = "system" | "light" | "dark";
export const THEME_KEY = "novelos.theme";
const listeners = new Set<() => void>();
const DARK_QUERY = "(prefers-color-scheme: dark)";

function readChoice(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch { return "system"; }
}

function systemDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_QUERY).matches;
}

/** The theme actually in effect once "system" is resolved. */
export function resolveTheme(choice: ThemeChoice = readChoice()): "light" | "dark" {
  return choice === "system" ? (systemDark() ? "dark" : "light") : choice;
}

export function getThemeChoice(): ThemeChoice {
  return readChoice();
}

/** Persist a choice and apply it to <html data-theme>. "system" removes the attribute so CSS follows the OS. */
export function setThemeChoice(choice: ThemeChoice) {
  try {
    if (choice === "system") window.localStorage.removeItem(THEME_KEY);
    else window.localStorage.setItem(THEME_KEY, choice);
  } catch { /* storage blocked: still apply for this page */ }
  applyTheme(choice);
  listeners.forEach((l) => l());
}

export function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

export function subscribeTheme(cb: () => void) {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === THEME_KEY) { applyTheme(readChoice()); cb(); }
  };
  const mq = typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
  window.addEventListener("storage", onStorage);
  mq?.addEventListener?.("change", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
    mq?.removeEventListener?.("change", cb);
  };
}


/** Inline, pre-paint: applies a stored explicit theme before React hydrates. */
export const THEME_BOOT_SCRIPT =
  `try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});` +
  `if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

