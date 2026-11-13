"use client";

import { clsx } from "clsx";
import {
  Bot, BookOpen, Brain, Download, Fingerprint, GitBranch, Globe, Image as ImageIcon,
  Library, LibraryBig, type LucideIcon, Plug, Search, Shield, SlidersHorizontal, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, qk } from "@/lib/api";
import { BrandLogo } from "./brand";

type Item = { href: string; label: string; icon: LucideIcon; exact?: boolean };

function projectNav(id: string): { title: string; items: Item[] }[] {
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
        { href: `${p}/publish`, label: "Publish and distribute", icon: Download },
      ],
    },
  ];
}

const SETTINGS: Item[] = [
  { href: "/settings/connections", label: "Connections", icon: Plug },
  { href: "/settings/agents", label: "Agents and models", icon: SlidersHorizontal },
];

export default function Sidebar() {
  const pathname = usePathname() ?? "/";
  const projectId = pathname.match(/^\/p\/([^/]+)/)?.[1];
  const { data: project } = useQuery({
    queryKey: projectId ? qk.project(projectId) : ["none"],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  });

  return (
    <aside className="flex w-[248px] shrink-0 flex-col gap-5 overflow-y-auto border-r border-rule bg-sheet px-3 py-5">
      <Link href="/" className="px-2"><BrandLogo /></Link>

      <button
        type="button"
        onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
        className="flex h-9 items-center gap-2 rounded-[8px] border border-rule bg-paper px-2.5 text-[13px] text-muted transition-colors hover:border-rule-strong"
      >
        <Search className="h-4 w-4" /> <span className="flex-1 text-left">Search or command</span>
        <kbd className="text-[11px]">Ctrl K</kbd>
      </button>

      <nav className="flex flex-col gap-4" aria-label="Main">
        <Group items={[{ href: "/", label: "Library", icon: Library, exact: true }]} pathname={pathname} />
        {projectId && (
          <>
            <div className="truncate px-2.5 text-[13px] font-semibold text-ink" title={project?.title}>
              {project?.title ?? "…"}
            </div>
            {projectNav(projectId).map((g) => (
              <Group key={g.title || "main"} title={g.title} items={g.items} pathname={pathname} />
            ))}
          </>
        )}
        <Group title="Settings" items={SETTINGS} pathname={pathname} />
      </nav>
    </aside>
  );
}

function Group({ title, items, pathname }: { title?: string; items: Item[]; pathname: string }) {
  return (
    <div className="flex flex-col gap-px">
      {title && <div className="label px-2.5 pb-1">{title}</div>}
      {items.map(({ href, label, icon: Icon, exact }) => {
        const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={clsx(
              "flex h-9 items-center gap-2.5 rounded-[8px] px-2.5 text-[14px] transition-colors",
              active ? "bg-paper font-semibold text-ink shadow-[0_0_0_1px_var(--color-rule)]" : "text-body hover:bg-paper hover:text-ink",
            )}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
            <span className="truncate">{label}</span>
          </Link>
        );
      })}
    </div>
  );
}
