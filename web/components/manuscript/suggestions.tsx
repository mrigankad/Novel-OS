"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Extension } from "@tiptap/react";
import type { Node as PMNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { clsx } from "clsx";
import { Check, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Badge } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import type { Chapter } from "@/lib/api/book";
import { sk, suggestionsApi, type Suggestion } from "@/lib/api/suggestions";

/* ---- ProseMirror highlights ---------------------------------------------------- */

export type Highlight = { id: string; quote: string };
type HlState = { items: Highlight[]; active: string | null; deco: DecorationSet };

export const suggestionKey = new PluginKey<HlState>("suggestions");

/** Find a quote inside one textblock (quotes never cross paragraphs). Returns doc positions. */
export function findQuote(doc: PMNode, quote: string): { from: number; to: number } | null {
  let hit: { from: number; to: number } | null = null;
  doc.descendants((node, pos) => {
    if (hit) return false;
    if (!node.isTextblock) return true;
    let text = "";
    const starts: { at: number; pos: number; len: number }[] = [];
    node.forEach((child, offset) => {
      const t = child.isText ? child.text ?? "" : child.type.name === "hardBreak" ? "\n" : "";
      starts.push({ at: text.length, pos: pos + 1 + offset, len: t.length || child.nodeSize });
      text += t;
    });
    const i = text.indexOf(quote);
    if (i < 0) return false;
    const toPos = (c: number) => {
      const seg = [...starts].reverse().find((s) => s.at <= c) ?? starts[0];
      return seg.pos + Math.min(c - seg.at, seg.len);
    };
    hit = { from: toPos(i), to: toPos(i + quote.length) };
    return false;
  });
  return hit;
}

function decorate(doc: PMNode, items: Highlight[], active: string | null): DecorationSet {
  const decos: Decoration[] = [];
  for (const it of items) {
    const r = findQuote(doc, it.quote);
    if (!r) continue;
    decos.push(Decoration.inline(r.from, r.to, {
      class: clsx("sugg-mark", it.id === active && "sugg-active"),
      "data-suggestion-id": it.id,
    }));
  }
  return DecorationSet.create(doc, decos);
}

/** Tiptap extension: track-changes highlights, fed by a `suggestionKey` meta; clicks fire SUGGESTION_CLICK. */
export const SUGGESTION_CLICK = "suggestion-click";

export const SuggestionHighlights = Extension.create({
  name: "suggestionHighlights",
  addProseMirrorPlugins() {
    return [new Plugin<HlState>({
      key: suggestionKey,
      state: {
        init: () => ({ items: [], active: null, deco: DecorationSet.empty }),
        apply(tr, prev) {
          const meta = tr.getMeta(suggestionKey) as { items: Highlight[]; active: string | null } | undefined;
          if (meta) return { ...meta, deco: decorate(tr.doc, meta.items, meta.active) };
          if (tr.docChanged) return { ...prev, deco: decorate(tr.doc, prev.items, prev.active) };
          return prev;
        },
      },
      props: {
        decorations: (state) => suggestionKey.getState(state)?.deco,
        handleDOMEvents: {
          click: (view, e) => {
            const el = (e.target as HTMLElement | null)?.closest?.("[data-suggestion-id]");
            const sid = el?.getAttribute("data-suggestion-id");
            if (sid) view.dom.dispatchEvent(new CustomEvent(SUGGESTION_CLICK, { detail: sid }));
            return false;
          },
        },
      },
    })];
  },
});

export const suggestionCss = `
  .prose-book .sugg-mark { background: var(--color-wash); text-decoration: underline dotted var(--color-gall); text-decoration-thickness: 1.5px; text-underline-offset: 4px; cursor: pointer; border-radius: 2px; transition: background-color .15s; }
  .prose-book .sugg-mark.sugg-active { background: color-mix(in srgb, var(--color-gall) 18%, transparent); }
`;

/* ---- Side panel -------------------------------------------------------------- */

const KIND_LABEL: Record<string, string> = {
  tighten: "Tighten", clarity: "Clarity", voice: "Voice", continuity: "Continuity", grammar: "Grammar",
};

export function useSuggestions(id: string, n: number) {
  return useQuery({ queryKey: sk.list(id, n), queryFn: () => suggestionsApi.list(id, n) });
}

export function SuggestionsPanel({
  id, n, items, activeId, onActive, beforeAction, onApplied,
}: {
  id: string;
  n: number;
  items: Suggestion[];
  activeId: string | null;
  onActive: (sid: string | null) => void;
  /** Save pending prose before the server changes the text. */
  beforeAction: () => Promise<void>;
  /** Called with the server's chapter after accepting; reload the editor from it. */
  onApplied: (c: Chapter) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [focus, setFocus] = useState("");
  const [runId, setRunId] = useState<string | null>(null);

  const run = useQuery({
    queryKey: sk.run(id, runId ?? "none"),
    queryFn: () => suggestionsApi.run(id, runId!),
    enabled: !!runId,
    refetchInterval: (q) => (["done", "failed", "cancelled"].includes(q.state.data?.status ?? "") ? false : 1500),
  });
  const status = run.data?.status;
  const running = !!runId && !["done", "failed", "cancelled"].includes(status ?? "");
  const failed = !!runId && status === "failed";

  const refresh = () => qc.invalidateQueries({ queryKey: sk.list(id, n) });

  const start = useMutation({
    mutationFn: async () => { await beforeAction(); return suggestionsApi.start(id, n, focus.trim()); },
    onSuccess: (r) => setRunId(r.run_id),
    onError: (e) => toast(`Couldn't ask the Editor: ${String(e)}`, "error"),
  });

  const done = (c: Chapter) => { onApplied(c); onActive(null); void refresh(); };
  const accept = useMutation({
    mutationFn: async (sid: string) => { await beforeAction(); return suggestionsApi.accept(id, n, sid); },
    onSuccess: done,
    onError: (e) => { toast(String(e).includes("409") ? "That passage has changed since the Editor read it." : String(e), "error"); void refresh(); },
  });
  const acceptAll = useMutation({
    mutationFn: async () => { await beforeAction(); return suggestionsApi.acceptAll(id, n); },
    onSuccess: done,
    onError: (e) => { toast(String(e), "error"); void refresh(); },
  });
  const dismiss = useMutation({
    mutationFn: (sid: string) => suggestionsApi.dismiss(id, n, sid),
    onSuccess: () => { onActive(null); void refresh(); },
    onError: (e) => toast(String(e), "error"),
  });

  // Refresh the list as soon as the run finishes (SSE also does this).
  const [seen, setSeen] = useState<string | null>(null);
  if (runId && status === "done" && seen !== runId) {
    setSeen(runId);
    void refresh();
  }

  const busy = accept.isPending || acceptAll.isPending;

  return (
    <aside aria-label="Editor suggestions" className="hidden w-[320px] shrink-0 flex-col border-l border-rule lg:flex">
      <div className="space-y-3 border-b border-rule p-4">
        <p className="eyebrow">Editor suggestions</p>
        <Input value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="Focus, e.g. tighten dialogue"
          aria-label="Suggestion focus" onKeyDown={(e) => { if (e.key === "Enter" && !running) start.mutate(); }} />
        <Button variant="ai" size="sm" className="w-full" disabled={running || start.isPending} onClick={() => start.mutate()}>
          <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} /> {running ? "Reading the chapter…" : "Suggest edits"}
        </Button>
        {running && (
          <div role="progressbar" aria-label="Editor is reading" className="relative h-0.5 overflow-hidden rounded-full bg-wash">
            <div className="absolute inset-y-0 w-1/3 animate-[sugg-slide_1.2s_ease-in-out_infinite] rounded-full bg-gall" />
            <style>{"@keyframes sugg-slide { from { left: -33%; } to { left: 100%; } }"}</style>
          </div>
        )}
        {failed && <p className="text-[12px] text-fail">The Editor couldn&apos;t finish: {run.data?.error || "unknown error"}</p>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {items.length === 0 && !running && (
          <p className="p-4 text-[13px] text-body">
            {runId && status === "done" ? "No edits worth making. The Editor is happy with this chapter." : "Ask the Editor for line edits. Nothing changes until you accept."}
          </p>
        )}
        {items.length > 1 && (
          <div className="flex items-center justify-between px-4 pt-3">
            <span className="text-[12px] text-body">{items.length} open</span>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => acceptAll.mutate()}>
              <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Accept all
            </Button>
          </div>
        )}
        <ul>
          {items.map((s) => (
            <li key={s.id} onMouseEnter={() => onActive(s.id)}
              className={clsx("border-b border-rule px-4 py-3 transition-colors", activeId === s.id && "bg-wash/60")}>
              <div className="mb-1.5 flex items-center gap-2">
                <Badge tone="ai">{KIND_LABEL[s.kind] ?? s.kind}</Badge>
              </div>
              <p className="font-prose text-[15px] leading-snug text-muted line-through">{s.quote}</p>
              <p className="mt-1 font-prose text-[15px] leading-snug text-ink">{s.replacement || <em className="text-muted">(delete)</em>}</p>
              {s.reason && <p className="mt-1.5 text-[12px] text-body">{s.reason}</p>}
              <div className="mt-2 flex gap-1.5">
                <Button size="sm" variant="secondary" disabled={busy} onClick={() => accept.mutate(s.id)}>
                  <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> Accept
                </Button>
                <Button size="sm" variant="ghost" disabled={dismiss.isPending} onClick={() => dismiss.mutate(s.id)}>
                  <X className="h-3.5 w-3.5" strokeWidth={1.75} /> Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
