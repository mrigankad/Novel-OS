import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { AnimatePresence, motion } from "motion/react";
import { api, type ProjectSummary, type ChapterSummary, type SearchHit } from "../api/client";

function currentProjectId(pathname: string): string | null {
  const m = pathname.match(/^\/projects\/([^/]+)/);
  return m ? m[1] : null;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

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

  // Clear the query as the palette closes, adjusted during render so the next
  // open never paints the previous search for a frame.
  const [lastOpen, setLastOpen] = useState(open);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (!open) setQuery("");
  }

  useEffect(() => {
    if (!open) return;
    api.projects().then(setProjects).catch(() => setProjects([]));
    const pid = currentProjectId(location.pathname);
    // No project in scope means the Chapters group is hidden by `pid &&` below,
    // so there is nothing to clear here.
    if (pid) api.chapters(pid).then(setChapters).catch(() => setChapters([]));
  }, [open, location.pathname]);

  const pid = currentProjectId(location.pathname);
  const searchable = open && !!pid && query.trim().length >= 2;

  useEffect(() => {
    if (!searchable || !pid) return;
    let cancelled = false;
    const t = window.setTimeout(() => {
      api.search(pid, query.trim())
        .then((rows) => { if (!cancelled) setHits(rows); })
        .catch(() => { if (!cancelled) setHits([]); });
    }, 120);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [searchable, pid, query]);

  // Derived, so a too-short or closed query hides stale results without an
  // extra state write.
  const visibleHits = searchable ? hits : [];

  const go = (path: string) => { navigate(path); setOpen(false); };

  function openHit(h: SearchHit) {
    if (!pid) return;
    if (h.kind === "chapter" && h.chapter != null) {
      go(`/projects/${pid}/chapters/${h.chapter}`);
      return;
    }
    if (h.kind === "relationship") {
      go(`/projects/${pid}/chart`);
      return;
    }
    go(`/projects/${pid}?codex=${encodeURIComponent(h.id)}`);
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-[#0c3bb8]/35 backdrop-blur-[6px]" onClick={() => setOpen(false)} aria-hidden />
          <motion.div
            initial={{ opacity: 0, y: 14, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ duration: 0.32, ease: [0.2, 0.9, 0.2, 1] }}
            className="glass-shell relative w-full max-w-lg overflow-hidden p-2.5"
          >
            <div className="glass-panel overflow-hidden">
              <Command label="Command Menu" className="flex flex-col" shouldFilter={visibleHits.length === 0}>
                <Command.Input
                  autoFocus
                  value={query}
                  onValueChange={setQuery}
                  placeholder={pid ? "Search Codex, chapters, or jump…" : "Jump to a project…"}
                  className="border-b border-[rgba(74,91,133,0.12)] bg-transparent px-5 py-4 text-[15px] text-ink-text outline-none placeholder:text-paper-muted"
                />
                <Command.List className="max-h-[52vh] overflow-y-auto p-2">
                  <Command.Empty className="px-3 py-6 text-center text-[13.5px] text-ink-muted">
                    No matches.
                  </Command.Empty>

                  <Group heading="Actions">
                    <Item onSelect={() => go("/")}>Go to Library</Item>
                    {pid && (
                      <Item onSelect={() => go(`/projects/${pid}/chart`)}>Open relationship chart</Item>
                    )}
                  </Group>

                  {pid && visibleHits.length > 0 && (
                    <Group heading="Search">
                      {visibleHits.map((h) => (
                        <Item
                          key={`${h.kind}-${h.id}`}
                          value={`${h.kind} ${h.label} ${h.subtitle || ""}`}
                          onSelect={() => openHit(h)}
                        >
                          <span className="capitalize text-[11px] text-paper-muted">{h.kind}</span>
                          <span className="ml-2 truncate">{h.label}</span>
                        </Item>
                      ))}
                    </Group>
                  )}

                  {pid && chapters.length > 0 && visibleHits.length === 0 && (
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
              <div className="flex items-center gap-3 border-t border-[rgba(74,91,133,0.12)] px-4 py-2 text-[11px] text-paper-muted">
                <span>↑↓ navigate</span><span>↵ open</span><span>esc close</span>
              </div>
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
      className="px-1 py-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[12px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:tracking-[-0.01em] [&_[cmdk-group-heading]]:text-paper-muted"
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
      className="flex cursor-pointer items-center rounded-xl px-3 py-2.5 text-[14px] text-ink-text data-[selected=true]:bg-[rgba(104,103,234,0.1)] data-[selected=true]:text-[var(--color-violet)]"
    >
      {children}
    </Command.Item>
  );
}
