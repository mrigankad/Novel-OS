"use client";

import { clsx } from "clsx";
import { ArrowLeft, ArrowRight, BookOpenCheck, List, MessageSquare, X } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrandMark } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Drawer } from "@/components/ui/drawer";
import { Textarea } from "@/components/ui/field";
import { ApiError } from "@/lib/api";
import { bk, paragraphs, readerApi, type BetaComment, type Reaction, type ReaderView } from "@/lib/api/beta";
import { REACTIONS, ReactionIcon } from "./reactions";

const SAVE_EVERY_MS = 15_000;

type Sel = { chapter: number; quote: string; from: number; to: number; x: number; y: number };

/** The public, distraction-free reader behind a beta link. No login, no studio chrome. */
export default function Reader({ token }: { token: string }) {
  const { data, error, isLoading } = useQuery({
    queryKey: bk.reader(token),
    queryFn: () => readerApi.get(token),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  if (isLoading) return <Shell><p className="py-24 text-center text-[15px] text-muted">Opening the book…</p></Shell>;
  if (error || !data) {
    const closed = error instanceof ApiError && error.status === 410;
    return (
      <Shell>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="font-display text-[28px] font-bold tracking-[-0.02em] text-ink">
            {closed ? "This reading round has closed" : "This link isn't valid"}
          </p>
          <p className="mt-3 text-[15px] text-body">
            {closed ? "Thank you for reading. The author is no longer collecting notes on this round."
              : "Check that you copied the whole link, or ask the author to send it again."}
          </p>
        </div>
      </Shell>
    );
  }
  return <Book token={token} view={data} />;
}

function Shell({ children, author, onChapters }: { children: React.ReactNode; author?: string; onChapters?: () => void }) {
  return (
    <div className="min-h-full bg-paper">
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-rule bg-paper/95 px-4 backdrop-blur sm:px-6">
        <BrandMark className="h-5 w-5" />
        <span className="min-w-0 flex-1 truncate text-[13px] text-body">
          {author ? <>Shared with you by <span className="font-semibold text-ink">{author}</span></> : "Novel OS"}
        </span>
        <ThemeToggle compact />
        {onChapters && (
          <button type="button" onClick={onChapters} aria-label="Chapters"
            className="flex h-9 items-center gap-1.5 rounded-[8px] px-2 text-[13px] text-body hover:bg-sheet hover:text-ink">
            <List className="h-[18px] w-[18px]" strokeWidth={1.75} /> <span className="hidden sm:inline">Chapters</span>
          </button>
        )}
      </header>
      {children}
    </div>
  );
}

function Book({ token, view }: { token: string; view: ReaderView }) {
  const qc = useQueryClient();
  const chapters = view.chapters;
  const startAt = useMemo(() => {
    const i = chapters.findIndex((c) => c.number === view.reader.furthest_chapter);
    return i >= 0 ? i : 0;
  }, [chapters, view.reader.furthest_chapter]);
  const [idx, setIdx] = useState(startAt);
  const [drawer, setDrawer] = useState(false);
  const [sel, setSel] = useState<Sel | null>(null);
  const [finished, setFinished] = useState(view.reader.finished);
  const ch = chapters[idx];
  const isLast = idx === chapters.length - 1;
  const paras = useMemo(() => (ch ? paragraphs(ch.text) : []), [ch]);
  const [percent, setPercent] = useState(0);
  const article = useRef<HTMLElement>(null);

  const progressFor = (n: number) => view.progress.find((p) => p.chapter === n)?.percent ?? 0;

  // ---- reading progress: IntersectionObserver marks the furthest paragraph seen; saved every ~15s.
  const seen = useRef(0);
  const lastSent = useRef({ percent: -1, at: 0 });
  const flush = useCallback((force = false) => {
    if (!ch) return;
    const p = seen.current;
    const now = Date.now();
    const seconds = document.visibilityState === "visible" ? Math.min(3600, Math.round((now - lastSent.current.at) / 1000)) : 0;
    if (!force && p === lastSent.current.percent && seconds < 5) return;
    lastSent.current = { percent: p, at: now };
    readerApi.progress(token, { chapter: ch.number, percent: p, seconds }).then((r) => {
      if (r.finished) setFinished(true);
    }).catch(() => { /* offline; next tick retries */ });
  }, [ch, token]);

  useEffect(() => {
    seen.current = ch ? progressFor(ch.number) : 0;
    setPercent(seen.current);
    lastSent.current = { percent: seen.current, at: Date.now() };
    const el = article.current;
    if (!el || !paras.length) return;
    const nodes = Array.from(el.querySelectorAll<HTMLElement>("[data-pi]"));
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        const i = Number((e.target as HTMLElement).dataset.pi);
        const pct = Math.round(((i + 1) / paras.length) * 100);
        if (pct > seen.current) { seen.current = pct; setPercent(pct); }
      }
    }, { threshold: 0.6 });
    nodes.forEach((n) => io.observe(n));
    const t = window.setInterval(() => flush(), SAVE_EVERY_MS);
    const onHide = () => { if (document.visibilityState === "hidden") flush(true); };
    document.addEventListener("visibilitychange", onHide);
    return () => {
      io.disconnect();
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", onHide);
      flush(true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ch?.number, paras.length]);

  const go = (i: number) => {
    setIdx(i);
    setSel(null);
    setDrawer(false);
    document.getElementById("main")?.scrollTo({ top: 0 });
    window.scrollTo({ top: 0 });
  };

  // ---- text selection -> floating bar
  useEffect(() => {
    const onUp = () => {
      const s = window.getSelection();
      if (!s || s.isCollapsed || !s.rangeCount || !ch) return;
      const range = s.getRangeAt(0);
      const startP = (range.startContainer.parentElement)?.closest<HTMLElement>("[data-start]");
      const endP = (range.endContainer.parentElement)?.closest<HTMLElement>("[data-start]");
      if (!startP || !endP || !article.current?.contains(startP)) return;
      const offsetIn = (p: HTMLElement, node: Node, off: number) => {
        const r = document.createRange();
        r.setStart(p, 0);
        r.setEnd(node, off);
        return Number(p.dataset.start) + r.toString().length;
      };
      const from = offsetIn(startP, range.startContainer, range.startOffset);
      const to = offsetIn(endP, range.endContainer, range.endOffset);
      const quote = ch.text.slice(from, to).trim();
      if (!quote) return;
      const rect = range.getBoundingClientRect();
      setSel({ chapter: ch.number, quote: quote.slice(0, 2000), from, to, x: rect.left + rect.width / 2, y: rect.top });
    };
    const onDown = (e: Event) => {
      if (!(e.target as HTMLElement).closest?.("[data-selbar]")) setSel(null);
    };
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointerdown", onDown);
    return () => { document.removeEventListener("pointerup", onUp); document.removeEventListener("pointerdown", onDown); };
  }, [ch]);

  const addComment = (c: BetaComment) =>
    qc.setQueryData<ReaderView>(bk.reader(token), (v) => (v ? { ...v, comments: [...v.comments, c] } : v));

  const byPara = useMemo(() => {
    const m = new Map<number, BetaComment[]>();
    if (!ch) return m;
    for (const c of view.comments.filter((x) => x.chapter === ch.number)) {
      let pi = paras.length - 1;
      const at = c.from_offset ?? 0;
      for (let i = 0; i < paras.length; i++) {
        if (paras[i].start > at) { pi = Math.max(0, i - 1); break; }
      }
      m.set(pi, [...(m.get(pi) ?? []), c]);
    }
    return m;
  }, [view.comments, ch, paras]);

  if (!ch) {
    return <Shell author={view.book.author}><p className="py-24 text-center text-body">No chapters were shared in this round.</p></Shell>;
  }

  return (
    <Shell author={view.book.author || "the author"} onChapters={() => setDrawer(true)}>
      <div className="sticky top-14 z-10 h-[3px] bg-rule" role="progressbar" aria-label="Chapter progress"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <div className="h-full bg-ink transition-[width] duration-500" style={{ width: `${percent}%` }} />
      </div>

      <div className="mx-auto max-w-[1060px] px-5 pb-24 pt-10 sm:px-8 sm:pt-16">
        <div className="lg:grid lg:grid-cols-[minmax(0,66ch)_220px] lg:gap-12">
          <div>
            <p className="text-[13px] text-muted">{view.book.title}</p>
            <h1 className="mt-2 font-display text-[32px] font-bold leading-[1.1] tracking-[-0.025em] text-ink sm:text-[40px]">
              <span className="block text-[15px] font-semibold tracking-normal text-muted">Chapter {ch.number}</span>
              {ch.title || `Chapter ${ch.number}`}
            </h1>
          </div>
        </div>

        <article ref={article} className="mt-10 prose-book selection:bg-wash" style={{ lineHeight: 1.75 }}>
          {paras.map((p, i) => (
            <div key={p.start} className="lg:grid lg:grid-cols-[minmax(0,66ch)_220px] lg:gap-12">
              <p data-pi={i} data-start={p.start} className="max-w-[66ch]">{p.text}</p>
              <MarginNotes notes={byPara.get(i) ?? []} />
            </div>
          ))}
        </article>

        <nav className="mt-16 flex max-w-[66ch] items-center justify-between gap-3 border-t border-rule pt-6">
          {idx > 0 ? (
            <Button variant="ghost" onClick={() => go(idx - 1)}>
              <ArrowLeft className="h-4 w-4" strokeWidth={1.75} /> Previous
            </Button>
          ) : <span />}
          {!isLast && (
            <Button onClick={() => { seen.current = 100; flush(true); go(idx + 1); }}>
              Next chapter <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
            </Button>
          )}
        </nav>

        {isLast && <FinishedMoment finished={finished} author={view.book.author}
          onReached={() => { seen.current = 100; setPercent(100); flush(true); }} />}
      </div>

      {sel && <SelectionBar sel={sel} token={token} onDone={(c) => { if (c) addComment(c); setSel(null); window.getSelection()?.removeAllRanges(); }} />}

      <Drawer open={drawer} onClose={() => setDrawer(false)} side="left" label="Chapters">
        <div className="flex min-h-full flex-col bg-paper px-4 py-6">
          <p className="px-2 font-display text-[20px] font-bold tracking-[-0.02em] text-ink">{view.book.title}</p>
          <p className="px-2 pb-4 text-[13px] text-muted">{view.round.name}</p>
          <ul className="flex flex-col gap-px">
            {chapters.map((c, i) => {
              const pct = i === idx ? percent : progressFor(c.number);
              return (
                <li key={c.number}>
                  <button type="button" onClick={() => go(i)} aria-current={i === idx ? "true" : undefined}
                    className={clsx("flex w-full items-baseline gap-3 rounded-[8px] px-2 py-2.5 text-left text-[14px] transition-colors",
                      i === idx ? "bg-sheet font-semibold text-ink" : "text-body hover:bg-sheet hover:text-ink")}>
                    <span className="w-6 shrink-0 text-muted">{c.number}</span>
                    <span className="min-w-0 flex-1 truncate">{c.title || `Chapter ${c.number}`}</span>
                    <span className="shrink-0 text-[12px] text-muted">{pct >= 95 ? "Read" : pct > 0 ? `${pct}%` : ""}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </Drawer>
    </Shell>
  );
}

function MarginNotes({ notes }: { notes: BetaComment[] }) {
  if (!notes.length) return <div className="hidden lg:block" />;
  return (
    <aside className="mb-6 flex flex-col gap-2 font-sans lg:mb-0 lg:pt-1">
      {notes.map((n) => (
        <div key={n.id} className="rounded-[10px] border border-rule bg-sheet px-3 py-2 text-[13px] leading-[1.45] text-body lg:border-0 lg:border-l-2 lg:border-rule-strong lg:bg-transparent lg:px-3 lg:py-0.5">
          <div className="flex items-center gap-1.5 text-ink">
            {n.reaction !== "none" && <ReactionIcon reaction={n.reaction} className="h-3.5 w-3.5" />}
            <span className="truncate italic text-muted">&ldquo;{n.quote.slice(0, 60)}{n.quote.length > 60 ? "…" : ""}&rdquo;</span>
          </div>
          {n.body && <p className="mt-1">{n.body}</p>}
        </div>
      ))}
    </aside>
  );
}

function SelectionBar({ sel, token, onDone }: { sel: Sel; token: string; onDone: (c?: BetaComment) => void }) {
  const [writing, setWriting] = useState(false);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const send = async (reaction: Reaction, text = "") => {
    setBusy(true);
    setErr("");
    try {
      const c = await readerApi.comment(token, { chapter: sel.chapter, quote: sel.quote, from_offset: sel.from, to_offset: sel.to, body: text, reaction });
      onDone(c);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't save that note");
      setBusy(false);
    }
  };

  const top = Math.max(64, sel.y - (writing ? 168 : 52));
  const left = typeof window !== "undefined" ? Math.min(Math.max(12, sel.x - (writing ? 160 : 110)), window.innerWidth - (writing ? 332 : 232)) : sel.x;

  return (
    <div data-selbar className="fixed z-30 rounded-[12px] bg-inverse p-1 text-on-inverse shadow-lg"
      style={{ top, left, width: writing ? 320 : undefined }} role="toolbar" aria-label="Note on selection">
      {writing ? (
        <form className="flex flex-col gap-2 p-1.5" onSubmit={(e) => { e.preventDefault(); if (body.trim()) void send("none", body); }}>
          <Textarea autoFocus rows={3} value={body} onChange={(e) => setBody(e.target.value)} placeholder="What did you think here?"
            className="text-[14px]" maxLength={4000} />
          {err && <p className="text-[12px]">{err}</p>}
          <div className="flex justify-end gap-1.5">
            <button type="button" onClick={() => onDone()} className="rounded-[8px] px-2.5 py-1.5 text-[13px] hover:bg-inverse-hover">Cancel</button>
            <button type="submit" disabled={busy || !body.trim()}
              className="rounded-[8px] bg-paper px-3 py-1.5 text-[13px] font-semibold text-ink disabled:opacity-50">Save note</button>
          </div>
        </form>
      ) : (
        <div className="flex items-center gap-0.5">
          <button type="button" onClick={() => setWriting(true)}
            className="flex h-9 items-center gap-1.5 rounded-[8px] px-2.5 text-[13px] font-semibold hover:bg-inverse-hover">
            <MessageSquare className="h-4 w-4" strokeWidth={1.75} /> Comment
          </button>
          <span className="mx-0.5 h-5 w-px bg-current opacity-20" aria-hidden />
          {REACTIONS.map(({ value, label, icon: Icon }) => (
            <button key={value} type="button" disabled={busy} onClick={() => void send(value)} aria-label={label} title={label}
              className="flex h-9 w-9 items-center justify-center rounded-[8px] hover:bg-inverse-hover">
              <Icon className="h-4 w-4" strokeWidth={1.75} />
            </button>
          ))}
          {err && <span className="px-2 text-[12px]">{err}</span>}
          <button type="button" onClick={() => onDone()} aria-label="Close"
            className="flex h-9 w-8 items-center justify-center rounded-[8px] opacity-70 hover:bg-inverse-hover">
            <X className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </div>
      )}
    </div>
  );
}

function FinishedMoment({ finished, author, onReached }: { finished: boolean; author: string; onReached: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(finished);
  const reached = useRef(onReached);
  useEffect(() => { reached.current = onReached; });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setShown(true); reached.current(); io.disconnect(); }
    }, { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className="mt-20 flex max-w-[66ch] flex-col items-center text-center">
      <BookOpenCheck className={clsx("h-8 w-8 text-ink transition-opacity duration-700", shown ? "opacity-100" : "opacity-0")} strokeWidth={1.75} />
      <p className={clsx("mt-4 font-display text-[30px] font-bold tracking-[-0.025em] text-ink transition-all duration-700",
        shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0")}>Finished</p>
      <p className="mt-2 max-w-sm font-prose text-[18px] italic leading-[1.6] text-body">
        Thank you for reading. Your notes go straight to {author || "the author"}. You can keep adding them until the round closes.
      </p>
    </div>
  );
}
