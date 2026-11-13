"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSONContent } from "@tiptap/react";
import { clsx } from "clsx";
import { Check, ChevronRight, Loader2, Plus, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChapterAgentPanel from "@/components/agents/chapter-panel";
import { fmt, StatusDot } from "@/components/manuscript/bits";
import { Binder } from "@/components/manuscript/binder";
import { FindingRow } from "@/components/manuscript/findings";
import { SuggestionsPanel, useSuggestions } from "@/components/manuscript/suggestions";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { actLabel, bk, bookApi, type Chapter, type ChapterPatch } from "@/lib/api/book";

const ProseEditor = dynamic(() => import("@/components/manuscript/editor"), {
  ssr: false,
  loading: () => <div className="space-y-3"><Skeleton className="h-5" /><Skeleton className="h-5" /><Skeleton className="h-5 w-2/3" /></div>,
});

type Mode = "plan" | "write" | "revise";
type SaveState = "idle" | "pending" | "saving" | "saved" | "error";

const countWords = (t: string) => (t.match(/[\p{L}\p{N}_][\p{L}\p{N}_'’-]*/gu) ?? []).length;
const isTyping = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));

export default function WritePage({ params }: { params: Promise<{ id: string; n: string }> }) {
  const { id, n } = use(params);
  return <Suspense><WriteScreen key={n} id={id} n={Number(n)} /></Suspense>;
}

function WriteScreen({ id, n }: { id: string; n: number }) {
  const router = useRouter();
  const search = useSearchParams();
  const qc = useQueryClient();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>(() => (["plan", "write", "revise"].includes(search.get("mode") ?? "") ? search.get("mode") as Mode : "write"));
  const [binderOpen, setBinderOpen] = useState(true);
  const chapters = useQuery({ queryKey: bk.chapters(id), queryFn: () => bookApi.chapters(id) });
  const chapter = useQuery({ queryKey: bk.chapter(id, n), queryFn: () => bookApi.chapter(id, n) });

  // ---- saving (debounced 800ms) ------------------------------------------------
  const pending = useRef<ChapterPatch>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [liveWords, setLiveWords] = useState<number | null>(null);

  const flush = useCallback(async () => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    const body = pending.current;
    if (!Object.keys(body).length) return;
    pending.current = {};
    setSave("saving");
    try {
      const saved = await bookApi.updateChapter(id, n, body);
      qc.setQueryData(bk.chapter(id, n), saved);
      void qc.invalidateQueries({ queryKey: bk.chapters(id) });
      void qc.invalidateQueries({ queryKey: ["p", id, "codex", "continuity"] });
      setSave(Object.keys(pending.current).length ? "pending" : "saved");
    } catch (e) {
      pending.current = { ...body, ...pending.current };
      setSave("error");
      toast(`Couldn't save: ${String(e)}`, "error");
    }
  }, [id, n, qc, toast]);

  const queue = useCallback((patch: ChapterPatch) => {
    pending.current = { ...pending.current, ...patch };
    setSave("pending");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), 800);
  }, [flush]);

  // Save whatever is left when leaving the chapter.
  useEffect(() => () => { void flush(); }, [flush]);

  const onEditorChange = useCallback((doc: JSONContent, text: string) => {
    setLiveWords(countWords(text));
    queue({ doc: doc as Record<string, unknown>, text });
  }, [queue]);

  // ---- keyboard: Ctrl+S snapshot, [ and ] for prev/next -------------------------
  const rows = chapters.data ?? [];
  const idx = rows.findIndex((c) => c.number === n);
  const prev = idx > 0 ? rows[idx - 1] : null;
  const next = idx >= 0 && idx < rows.length - 1 ? rows[idx + 1] : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void (async () => {
          await flush();
          try {
            await bookApi.snapshot(id, n, "Manual snapshot");
            void qc.invalidateQueries({ queryKey: bk.versions(id, n) });
            toast("Snapshot saved", "success");
          } catch (err) { toast(String(err), "error"); }
        })();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return;
      if (e.key === "[" && prev) router.push(`/p/${id}/write/${prev.number}`);
      if (e.key === "]" && next) router.push(`/p/${id}/write/${next.number}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flush, id, n, prev, next, qc, router, toast]);

  // ---- Editor suggestions (Revise mode) -----------------------------------------
  const suggestions = useSuggestions(id, n);
  const [activeSugg, setActiveSugg] = useState<string | null>(null);
  const [editorRev, setEditorRev] = useState(0);
  const openSugg = useMemo(() => (mode === "revise" ? suggestions.data ?? [] : []), [mode, suggestions.data]);
  const highlights = useMemo(() => openSugg.map((s) => ({ id: s.id, quote: s.quote })), [openSugg]);
  const onApplied = useCallback((saved: Chapter) => {
    qc.setQueryData(bk.chapter(id, n), saved);
    void qc.invalidateQueries({ queryKey: bk.chapters(id) });
    void qc.invalidateQueries({ queryKey: bk.versions(id, n) });
    setLiveWords(null);
    setEditorRev((r) => r + 1); // remount the editor from the server text
  }, [id, n, qc]);

  const c = chapter.data;
  const words = liveWords ?? c?.word_count ?? 0;

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-rule px-5">
        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px] text-body">
          <Link href={`/p/${id}`} className="hover:text-ink">{c ? actLabel(c.act) : "…"}</Link>
          <ChevronRight className="h-3.5 w-3.5 text-muted" strokeWidth={1.75} />
          <span className="truncate font-semibold text-ink">Chapter {n}</span>
        </nav>
        <div role="tablist" aria-label="Mode" className="flex rounded-[10px] bg-sheet p-0.5">
          {(["plan", "write", "revise"] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
              className={clsx("h-8 rounded-[8px] px-3.5 text-[13px] font-semibold capitalize transition-colors",
                mode === m ? "bg-paper text-ink shadow-[0_1px_2px_rgba(20,19,26,0.08)]" : "text-body hover:text-ink")}>
              {m}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4 text-[13px]">
          <SaveIndicator state={save} />
          <span className="text-body"><span className="font-semibold text-ink">{fmt(words)}</span> / {fmt(c?.target_words ?? 0)}</span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <Binder projectId={id} chapters={rows} current={n} open={binderOpen} onToggle={() => setBinderOpen((o) => !o)} />
        <div className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[680px] px-6 pt-14">
            {chapter.isLoading && <Skeleton className="h-12 w-2/3" />}
            {chapter.error && <p className="text-[14px] text-fail">This chapter doesn&apos;t exist. <Link className="underline" href={`/p/${id}`}>Back to the manuscript</Link></p>}
            {c && (
              <div key={c.id}>
                <TitleField c={c} onSave={(title) => queue({ title })} />
                <p className="mb-10 mt-3 flex items-center gap-2 text-[13px] text-body">
                  <StatusDot status={c.status} /> {c.status}{c.pov && <> · {c.pov}</>}
                </p>
                {mode === "plan" && <PlanFields c={c} queue={queue} />}
                {mode === "revise" && <ChapterFindings id={id} n={n} />}
                {/* Kept mounted in Plan mode so unsaved prose never resets. */}
                <div className={mode === "plan" ? "hidden" : undefined}>
                  <ProseEditor key={editorRev} initialDoc={c.doc} initialText={c.text} onChange={onEditorChange}
                    highlights={highlights} activeHighlight={activeSugg} onHighlightClick={setActiveSugg} />
                </div>
              </div>
            )}
          </div>
        </div>
        {mode === "revise" && c && (
          <SuggestionsPanel id={id} n={n} items={openSugg} activeId={activeSugg} onActive={setActiveSugg}
            beforeAction={flush} onApplied={onApplied} />
        )}
        <ChapterAgentPanel projectId={id} chapter={n} />
      </div>
    </div>
  );
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === "idle") return null;
  if (state === "error") return <span className="text-fail">Not saved</span>;
  if (state === "saved") return <span className="flex items-center gap-1 text-muted"><Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Saved</span>;
  return <span className="flex items-center gap-1 text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} /> Saving</span>;
}

function TitleField({ c, onSave }: { c: Chapter; onSave: (title: string) => void }) {
  const [title, setTitle] = useState(c.title);
  return (
    <input
      aria-label="Chapter title"
      value={title}
      placeholder="Untitled chapter"
      onChange={(e) => { setTitle(e.target.value); onSave(e.target.value); }}
      className="w-full bg-transparent font-prose text-[44px] font-medium leading-[1.1] tracking-[-0.01em] text-ink outline-none placeholder:text-rule-strong"
    />
  );
}

function PlanFields({ c, queue }: { c: Chapter; queue: (p: ChapterPatch) => void }) {
  const [synopsis, setSynopsis] = useState(c.synopsis);
  const [pov, setPov] = useState(c.pov);
  const [status, setStatus] = useState(c.status);
  const [target, setTarget] = useState(String(c.target_words));
  const [beats, setBeats] = useState<string[]>(c.beats ?? []);
  const setBeatsAndSave = (b: string[]) => { setBeats(b); queue({ beats: b }); };

  return (
    <div className="space-y-8 pb-24">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Point of view"><Input value={pov} onChange={(e) => { setPov(e.target.value); queue({ pov: e.target.value }); }} placeholder="Whose eyes?" /></Field>
        <Field label="Status">
          <select value={status} onChange={(e) => { setStatus(e.target.value); queue({ status: e.target.value }); }}
            className="h-10 rounded-[10px] border border-rule-strong bg-paper px-3 text-[14px]">
            {["planned", "drafting", "drafted", "revising", "final"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Target words"><Input inputMode="numeric" value={target} onChange={(e) => {
          const v = e.target.value.replace(/\D/g, ""); setTarget(v); if (v) queue({ target_words: Number(v) });
        }} /></Field>
      </div>
      <Field label="Synopsis">
        <Textarea value={synopsis} rows={4} className="font-prose text-[17px]" placeholder="What happens, and what changes?"
          onChange={(e) => { setSynopsis(e.target.value); queue({ synopsis: e.target.value }); }} />
      </Field>
      <div>
        <p className="mb-2 text-[12px] font-semibold text-ink">Beats</p>
        <ol className="space-y-2">
          {beats.map((b, i) => (
            <li key={i} className="flex items-center gap-3">
              <span className="w-5 text-right text-[13px] text-muted">{i + 1}</span>
              <Input value={b} onChange={(e) => setBeatsAndSave(beats.map((x, j) => (j === i ? e.target.value : x)))} />
              <button type="button" aria-label={`Remove beat ${i + 1}`} onClick={() => setBeatsAndSave(beats.filter((_, j) => j !== i))}
                className="rounded-[8px] p-2 text-muted hover:bg-sheet hover:text-ink"><X className="h-4 w-4" strokeWidth={1.75} /></button>
            </li>
          ))}
        </ol>
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => setBeatsAndSave([...beats, ""])}>
          <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add beat
        </Button>
      </div>
    </div>
  );
}

function ChapterFindings({ id, n }: { id: string; n: number }) {
  const q = useQuery({ queryKey: bk.continuity(id, n), queryFn: () => bookApi.continuity(id, n), staleTime: 0 });
  const findings = q.data?.findings ?? [];
  return (
    <section className="mb-10 border-y border-rule py-4">
      <div className="flex items-center justify-between">
        <p className="label">Continuity in this chapter</p>
        <Link href={`/p/${id}/continuity`} className="text-[12px] text-body hover:text-ink">All findings</Link>
      </div>
      {q.isLoading && <Skeleton className="mt-3 h-10" />}
      {q.data && findings.length === 0 && <p className="mt-3 text-[13px] text-body">Nothing to flag. The Codex and this chapter agree.</p>}
      {findings.length > 0 && <ul className="mt-1">{findings.map((f) => <FindingRow key={f.key} projectId={id} finding={f} compact />)}</ul>}
    </section>
  );
}
