"use client";

import { clsx } from "clsx";
import {
  Bot, BookOpen, Brain, Download, Fingerprint, GitBranch, Globe, Headphones, Image as ImageIcon,
  Library, LibraryBig, type LucideIcon, PanelLeftClose, PanelLeftOpen, Plug, Search, Shield,
  SlidersHorizontal, Users, Users2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, qk } from "@/lib/api";
import { BrandLogo, BrandMark } from "./brand";
import { ThemeToggle } from "./theme-toggle";

type Item = { href: string; label: string; icon: LucideIcon; exact?: boolean };
type NavGroup = { title: string; items: Item[] };

function projectNav(id: string): NavGroup[] {
  const p = `/p/${id}`;
  return [
    { title: "", items: [{ href: p, label: "Manuscript", icon: BookOpen, exact: true }] },
    {
      title: "Studio",
      items: [
        { href: `${p}/room`, label: "Agent room", icon: Bot },
        { href: `${p}/research`, label: "Research swarm", icon: Globe },
        { href: `${p}/voice`, label: "Voice Lab", icon: Fingerprint },
        { href: `${p}/codex`, label: "Codex", icon: Users },
        { href: `${p}/continuity`, label: "Continuity", icon: Shield },
        { href: `${p}/memory`, label: "Memory", icon: Brain },
        { href: `${p}/versions`, label: "Drafts and versions", icon: GitBranch },
      ],
    },
    {
      title: "Ship",
      items: [
        { href: `${p}/media`, label: "Media and images", icon: ImageIcon },
        { href: `${p}/cover`, label: "Cover studio", icon: LibraryBig },
        { href: `${p}/audio`, label: "Audiobook", icon: Headphones },
        { href: `${p}/publish`, label: "Publish and distribute", icon: Download },
        { href: `${p}/beta`, label: "Beta readers", icon: Users2 },
      ],
    },
  ];
}

const LIBRARY: Item[] = [{ href: "/", label: "Library", icon: Library, exact: true }];
const SETTINGS: Item[] = [
  { href: "/settings/connections", label: "Connections", icon: Plug },
  { href: "/settings/agents", label: "Agents and models", icon: SlidersHorizontal },
];

/** One source for the nav, shared by the desktop sidebar/rail and the mobile drawer. */
export function useNav() {
  const pathname = usePathname() ?? "/";
  const projectId = pathname.match(/^\/p\/([^/]+)/)?.[1];
  const { data: project } = useQuery({
    queryKey: projectId ? qk.project(projectId) : ["none"],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  });
  return {
    pathname, projectId,
    projectTitle: projectId ? project?.title ?? "…" : undefined,
    groups: projectId ? projectNav(projectId) : [],
  };
}

export const openCommandPalette = () =>
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }));

// ---- rail collapse, persisted -------------------------------------------------
const RAIL_KEY = "novelos.rail";
const railListeners = new Set<() => void>();
function readRail() {
  try { return window.localStorage.getItem(RAIL_KEY) === "1"; } catch { return false; }
}
function setRail(collapsed: boolean) {
  try { window.localStorage.setItem(RAIL_KEY, collapsed ? "1" : "0"); } catch { /* storage blocked */ }
  railListeners.forEach((l) => l());
}
function subscribeRail(cb: () => void) {
  railListeners.add(cb);
  return () => { railListeners.delete(cb); };
}

export function NavList({ rail = false, onNavigate }: { rail?: boolean; onNavigate?: () => void }) {
  const { pathname, projectId, projectTitle, groups } = useNav();
  return (
    <nav className="flex flex-col gap-4" aria-label="Main">
      <Group items={LIBRARY} pathname={pathname} rail={rail} onNavigate={onNavigate} />
      {projectId && (
        <>
          {rail ? <div className="mx-2 border-t border-rule" aria-hidden /> : (
            <div className="truncate px-2.5 text-[13px] font-semibold text-ink" title={projectTitle}>{projectTitle}</div>
          )}
          {groups.map((g) => (
            <Group key={g.title || "main"} title={g.title} items={g.items} pathname={pathname} rail={rail} onNavigate={onNavigate} />
          ))}
        </>
      )}
      <Group title="Settings" items={SETTINGS} pathname={pathname} rail={rail} onNavigate={onNavigate} />
    </nav>
  );
}

/**
 * Desktop navigation. md to lg: icon rail. lg and up: the full 248px sidebar,
 * or the rail when the writer collapses it. Below md, MobileNav takes over.
 */
export default function Sidebar() {
  const collapsed = useSyncExternalStore(subscribeRail, readRail, () => false);
  // The public beta reader (/read/[token]) has no studio chrome.
  if (usePathname()?.startsWith("/read/")) return null;
  return (
    <>
      <Rail className={collapsed ? "hidden md:flex" : "hidden md:flex lg:hidden"} canExpand={collapsed} />
      {!collapsed && (
        <aside className="hidden w-[248px] shrink-0 flex-col gap-5 overflow-y-auto border-r border-rule bg-sheet px-3 py-5 lg:flex">
          <div className="flex items-center justify-between gap-2 pl-2">
            <Link href="/"><BrandLogo /></Link>
            <button type="button" onClick={() => setRail(true)} aria-label="Collapse sidebar" title="Collapse sidebar"
              className="rounded-[8px] p-1.5 text-muted hover:bg-paper hover:text-ink">
              <PanelLeftClose className="h-4 w-4" strokeWidth={1.75} />
            </button>
          </div>

          <button type="button" onClick={openCommandPalette}
            className="flex h-9 items-center gap-2 rounded-[8px] border border-rule bg-paper px-2.5 text-[13px] text-muted transition-colors hover:border-rule-strong">
            <Search className="h-4 w-4" strokeWidth={1.75} /> <span className="flex-1 text-left">Search or command</span>
            <kbd className="text-[11px]">Ctrl K</kbd>
          </button>

          <NavList />
          <div className="mt-auto pt-2"><ThemeToggle /></div>
        </aside>
      )}
    </>
  );
}

function Rail({ className, canExpand }: { className: string; canExpand: boolean }) {
  return (
    <aside className={clsx("w-[60px] shrink-0 flex-col gap-4 overflow-y-auto border-r border-rule bg-sheet px-2 py-5", className)}>
      <Link href="/" aria-label="Novel OS, Library" className="flex justify-center"><BrandMark /></Link>
      <button type="button" onClick={openCommandPalette} aria-label="Search or command" title="Search or command (Ctrl K)"
        className="flex h-9 items-center justify-center rounded-[8px] text-body hover:bg-paper hover:text-ink">
        <Search className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </button>
      <NavList rail />
      <div className="mt-auto flex flex-col items-center gap-1 pt-2">
        <ThemeToggle compact />
        {canExpand && (
          <button type="button" onClick={() => setRail(false)} aria-label="Expand sidebar" title="Expand sidebar"
            className="hidden h-9 w-9 items-center justify-center rounded-[8px] text-body hover:bg-paper hover:text-ink lg:flex">
            <PanelLeftOpen className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </button>
        )}
      </div>
    </aside>
  );
}

function Group({ title, items, pathname, rail, onNavigate }: {
  title?: string; items: Item[]; pathname: string; rail?: boolean; onNavigate?: () => void;
}) {
  return (
    <div className="flex flex-col gap-px">
      {title && !rail && <div className="label px-2.5 pb-1">{title}</div>}
      {items.map(({ href, label, icon: Icon, exact }) => {
        const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            aria-label={rail ? label : undefined}
            title={rail ? label : undefined}
            className={clsx(
              "flex h-9 items-center gap-2.5 rounded-[8px] text-[14px] transition-colors",
              rail ? "justify-center" : "px-2.5",
              active ? "bg-paper font-semibold text-ink shadow-[0_0_0_1px_var(--color-rule)]" : "text-body hover:bg-paper hover:text-ink",
            )}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} aria-hidden />
            {!rail && <span className="truncate">{label}</span>}
          </Link>
        );
      })}
    </div>
  );
}
