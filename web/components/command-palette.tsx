"use client";

import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { BookOpen, FileText, Plus, Users } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { projectsApi, qk } from "@/lib/api";
import { bk, bookApi } from "@/lib/api/book";

/** Ctrl/Cmd+K: jump to a book, a chapter or a Codex entry. Mounted once in the root layout. */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const projectId = pathname.match(/^\/p\/([^/]+)/)?.[1];

  useEffect(() => {
    // Listen on window: the sidebar's search button dispatches its keydown there.
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const books = useQuery({ queryKey: qk.projects, queryFn: projectsApi.list, enabled: open });
  const chapters = useQuery({ queryKey: bk.chapters(projectId ?? ""), queryFn: () => bookApi.chapters(projectId!), enabled: open && !!projectId });
  const codex = useQuery({ queryKey: bk.codex(projectId ?? ""), queryFn: () => bookApi.codex(projectId!), enabled: open && !!projectId });

  const go = (href: string) => { setOpen(false); router.push(href); };

  // Public reader pages are not the studio: no palette, no studio queries.
  if (pathname?.startsWith("/read/")) return null;

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Jump to"
      overlayClassName="fixed inset-0 z-40 bg-[rgba(20,19,26,0.18)]"
      contentClassName="fixed left-1/2 top-[14vh] z-50 w-[min(600px,92vw)] -translate-x-1/2 overflow-hidden rounded-[16px] bg-paper shadow-[0_24px_64px_rgba(20,19,26,0.22)] ring-1 ring-rule"
    >
      <Command.Input
        placeholder="Jump to a book, chapter or Codex entry…"
        className="h-14 w-full border-b border-rule bg-transparent px-5 text-[16px] text-ink outline-none placeholder:text-muted"
      />
      <Command.List className="max-h-[56vh] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-[14px] text-body">No matches.</Command.Empty>
        {projectId && !!chapters.data?.length && (
          <Group heading="Chapters">
            {chapters.data.map((c) => (
              <Row key={c.id} value={`chapter ${c.number} ${c.title}`} onSelect={() => go(`/p/${projectId}/write/${c.number}`)}
                icon={<FileText className="h-4 w-4" strokeWidth={1.75} />} hint={`Chapter ${c.number}`}>
                {c.title || "Untitled"}
              </Row>
            ))}
          </Group>
        )}
        {projectId && !!codex.data?.length && (
          <Group heading="Codex">
            {codex.data.map((e) => (
              <Row key={e.id} value={`codex ${e.name} ${e.aliases.join(" ")}`} onSelect={() => go(`/p/${projectId}/codex?entry=${e.id}`)}
                icon={<Users className="h-4 w-4" strokeWidth={1.75} />} hint={e.kind}>
                {e.name}
              </Row>
            ))}
          </Group>
        )}
        <Group heading="Books">
          {books.data?.map((p) => (
            <Row key={p.id} value={`book ${p.title} ${p.genre}`} onSelect={() => go(`/p/${p.id}`)}
              icon={<BookOpen className="h-4 w-4" strokeWidth={1.75} />} hint={p.genre}>
              {p.title}
            </Row>
          ))}
          <Row value="new book create" onSelect={() => go("/?new=1")} icon={<Plus className="h-4 w-4" strokeWidth={1.75} />}>
            New book
          </Row>
        </Group>
      </Command.List>
    </Command.Dialog>
  );
}

function Group({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <Command.Group heading={heading}
      className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.1em] [&_[cmdk-group-heading]]:text-muted">
      {children}
    </Command.Group>
  );
}

function Row({ value, onSelect, icon, hint, children }: { value: string; onSelect: () => void; icon: ReactNode; hint?: string; children: ReactNode }) {
  return (
    <Command.Item value={value} onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-[10px] px-3 py-2.5 text-[14px] text-ink data-[selected=true]:bg-sheet">
      <span className="text-muted">{icon}</span>
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {hint && <span className="text-[12px] capitalize text-muted">{hint}</span>}
    </Command.Item>
  );
}
