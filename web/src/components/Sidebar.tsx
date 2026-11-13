import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import BrandMark, { BrandLogo } from "./BrandMark";
import Icon, { type IconName } from "./Icon";

const STORAGE_KEY = "novelos-sidebar-collapsed";

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(loadCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch { /* ignore */ }
  }, [collapsed]);

  return (
    <aside
      className={`glass-rail flex shrink-0 flex-col text-ink-text transition-[width] duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
        collapsed ? "w-[64px]" : "w-[248px]"
      }`}
      data-collapsed={collapsed ? "true" : "false"}
    >
      <div className={`flex items-center pt-5 pb-4 ${collapsed ? "justify-center px-2" : "justify-between px-4"}`}>
        {collapsed ? <BrandMark className="h-7 w-7" /> : <BrandLogo />}
        {!collapsed && (
          <CollapseButton collapsed={collapsed} onClick={() => setCollapsed(true)} />
        )}
      </div>

      <nav className={`flex flex-col gap-0.5 ${collapsed ? "px-2" : "px-3"}`}>
        <button
          type="button"
          title="Search or command"
          aria-label="Search or command"
          onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
          className={`mb-3 flex h-9 items-center rounded-lg border border-paper-line bg-paper text-[13px] text-paper-muted transition-colors hover:border-ink-line hover:text-ink-text ${
            collapsed ? "justify-center px-0" : "justify-between gap-2 px-2.5"
          }`}
        >
          <span className="flex items-center gap-2">
            <Icon name="search" className="h-4 w-4" />
            {!collapsed && "Search or command"}
          </span>
          {!collapsed && <kbd className="text-[11px] font-medium">Ctrl K</kbd>}
        </button>

        <SideLink to="/" label="Library" icon="library" end collapsed={collapsed} />

        {!collapsed && <SectionLabel>Settings</SectionLabel>}
        <SideLink to="/settings" label="Connections" icon="plug" collapsed={collapsed} />
      </nav>

      <div className={`mt-auto pb-4 ${collapsed ? "flex justify-center px-2" : "px-4"}`}>
        {collapsed ? (
          <CollapseButton collapsed={collapsed} onClick={() => setCollapsed(false)} />
        ) : (
          <p className="text-[12px] leading-relaxed text-paper-muted">
            Structure first. Prose second. Continuity always.
          </p>
        )}
      </div>
    </aside>
  );
}

function CollapseButton({ collapsed, onClick }: { collapsed: boolean; onClick: () => void }) {
  const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-expanded={!collapsed}
      title={label}
      className="flex h-7 w-7 items-center justify-center rounded-md text-paper-muted transition-colors hover:bg-paper hover:text-ink-text"
    >
      <Icon
        name="chevron-right"
        className={`h-4 w-4 transition-transform duration-300 ${collapsed ? "" : "rotate-180"}`}
      />
    </button>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <div className="px-2.5 pt-5 pb-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-paper-muted">
      {children}
    </div>
  );
}

function SideLink({
  to, label, icon, end, collapsed,
}: {
  to: string; label: string; icon: IconName; end?: boolean; collapsed?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      title={label}
      aria-label={label}
      className={({ isActive }) =>
        `flex h-9 items-center gap-2.5 rounded-lg text-[14px] transition-colors duration-150 ${
          collapsed ? "justify-center px-0" : "px-2.5"
        } ${
          isActive
            ? "bg-paper font-semibold text-ink-text shadow-[0_0_0_1px_var(--color-paper-line)]"
            : "text-ink-muted hover:bg-paper hover:text-ink-text"
        }`
      }
    >
      <Icon name={icon} className="h-[18px] w-[18px]" />
      {!collapsed && <span className="leading-none">{label}</span>}
    </NavLink>
  );
}
