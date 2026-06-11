import { NavLink } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";

function OwlMark() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="#161d2e" stroke="#f4b740" strokeWidth="1.2" />
      <path d="M9 11c0-2 2-3 3-1m11 1c0-2-2-3-3-1" stroke="#f4b740" strokeWidth="1.4" fill="none" strokeLinecap="round" />
      <circle cx="12" cy="16" r="3.4" fill="#0e1320" stroke="#f4b740" strokeWidth="1.1" />
      <circle cx="20" cy="16" r="3.4" fill="#0e1320" stroke="#f4b740" strokeWidth="1.1" />
      <circle cx="12" cy="16" r="1.2" fill="#f4b740" />
      <circle cx="20" cy="16" r="1.2" fill="#f4b740" />
      <path d="M16 19l-1.6 2.4h3.2L16 19z" fill="#f4b740" />
    </svg>
  );
}

export default function Sidebar() {
  return (
    <aside className="flex w-[244px] shrink-0 flex-col bg-ink text-[#c8cedd]">
      <div className="flex items-center justify-between px-5 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <OwlMark />
          <div className="leading-tight">
            <div className="font-display text-[19px] font-semibold tracking-tight text-white">
              Novel OS
            </div>
            <div className="text-[10.5px] uppercase tracking-[0.18em] text-amber/90">
              Manuscript Desk
            </div>
          </div>
        </div>
        <ThemeToggle />
      </div>

      <div className="mx-5 mb-4 h-px bg-ink-line" />

      <nav className="flex flex-col gap-0.5 px-3">
        <button
          onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          className="mb-1 flex items-center justify-between rounded-lg px-3 py-2 text-[13px] text-[#aab2c4] transition-colors hover:bg-ink-800"
        >
          <span>Search…</span>
          <kbd className="rounded border border-ink-line px-1.5 py-0.5 text-[10px] text-[#9aa3b8]">⌘K</kbd>
        </button>
        <SideLink to="/" label="Library" hint="All projects" />
      </nav>

      <div className="mt-auto px-5 pb-5 pt-6">
        <div className="rounded-lg border border-ink-line/70 bg-ink-800/60 p-3.5">
          <p className="font-display text-[13px] italic text-[#aeb6c8]">
            “Write novels like a build pipeline.”
          </p>
        </div>
        <p className="mt-3 text-[10.5px] tracking-wide text-[#8b93a8]">
          v0.2.0 · local
        </p>
      </div>
    </aside>
  );
}

function SideLink({ to, label, hint }: { to: string; label: string; hint: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `group flex flex-col rounded-lg px-3 py-2 transition-colors ${
          isActive ? "bg-ink-700 text-white" : "text-[#aab2c4] hover:bg-ink-800"
        }`
      }
    >
      <span className="text-[13.5px] font-medium">{label}</span>
      <span className="text-[11px] text-[#9aa3b8]">{hint}</span>
    </NavLink>
  );
}
