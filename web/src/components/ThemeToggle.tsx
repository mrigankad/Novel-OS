import { useState } from "react";
import { getTheme, setTheme, type Theme } from "../theme";

export default function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>(getTheme());
  const next = theme === "dark" ? "light" : "dark";

  function toggle() {
    setTheme(next);
    setThemeState(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-[#9aa3b8] transition-colors hover:bg-ink-800 hover:text-white"
    >
      {theme === "dark" ? (
        // sun
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" strokeLinecap="round" />
        </svg>
      ) : (
        // moon
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}
