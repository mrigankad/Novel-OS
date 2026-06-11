import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { AnimatePresence, motion } from "motion/react";
import { api, type ProjectSummary, type ChapterSummary } from "../api/client";
import { getTheme, setTheme } from "../theme";

function currentProjectId(pathname: string): string | null {
  const m = pathname.match(/^\/projects\/([^/]+)/);
  return m ? m[1] : null;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

  // Global ⌘K / Ctrl-K toggle
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    api.projects().then(setProjects).catch(() => setProjects([]));
    const pid = currentProjectId(location.pathname);
    if (pid) api.chapters(pid).then(setChapters).catch(() => setChapters([]));
    else setChapters([]);
  }, [open, location.pathname]);

  const pid = currentProjectId(location.pathname);
  const go = (path: string) => { navigate(path); setOpen(false); };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-ink/50 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden />
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-paper-line bg-paper-card shadow-[var(--shadow-lift)]"
          >
            <Command label="Command Menu" className="flex flex-col">
              <Command.Input
                autoFocus
                placeholder="Jump to a project or chapter, or run a command…"
                className="border-b border-paper-line bg-transparent px-5 py-4 text-[15px] text-ink-text outline-none placeholder:text-paper-muted"
              />
              <Command.List className="max-h-[52vh] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-[13.5px] text-ink-muted">
                  No matches.
                </Command.Empty>

                <Group heading="Actions">
                  <Item onSelect={() => go("/")}>Go to Library</Item>
                  <Item onSelect={() => { const t = getTheme() === "dark" ? "light" : "dark"; setTheme(t); setOpen(false); }}>
                    Toggle theme
                  </Item>
                </Group>

                {pid && chapters.length > 0 && (
                  <Group heading="Chapters">
                    {chapters.map((c) => (
                      <Item key={c.number} value={`chapter ${c.number} ${c.title}`}
                            onSelect={() => go(`/projects/${pid}/chapters/${c.number}`)}>
                        <span className="font-mono text-[11px] text-paper-muted">Ch {c.number}</span>
                        <span className="ml-2">{c.title || "Untitled"}</span>
                      </Item>
                    ))}
                  </Group>
                )}

                <Group heading="Projects">
                  {projects.map((p) => (
                    <Item key={p.id} value={`project ${p.title} ${p.genre}`}
                          onSelect={() => go(`/projects/${p.id}`)}>
                      {p.title}
                      <span className="ml-2 text-[12px] text-ink-muted">{p.genre}</span>
                    </Item>
                  ))}
                </Group>
              </Command.List>
            </Command>
            <div className="flex items-center gap-3 border-t border-paper-line px-4 py-2 text-[11px] text-paper-muted">
              <span>↑↓ navigate</span><span>↵ open</span><span>esc close</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10.5px] [&_[cmdk-group-heading]]:font-bold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-paper-muted"
    >
      {children}
    </Command.Group>
  );
}

function Item({ children, onSelect, value }: { children: React.ReactNode; onSelect: () => void; value?: string }) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center rounded-lg px-3 py-2.5 text-[14px] text-ink-text data-[selected=true]:bg-ink/[0.06]"
    >
      {children}
    </Command.Item>
  );
}
