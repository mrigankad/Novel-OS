"use client";

import { clsx } from "clsx";
import { SendHorizontal } from "lucide-react";
import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { Agent } from "@/lib/api/agents";
import { Button } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";
import { AgentGlyph } from "./agent-icon";

/** Message box with @-mention autocomplete over the cast. */
export function Composer({ agents, onSend, disabled }: {
  agents: Agent[]; onSend: (body: string) => void; disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLTextAreaElement>(null);

  const matches = useMemo(() => {
    if (query === null) return [];
    const q = query.toLowerCase();
    return agents.filter((a) => a.enabled && (a.name.toLowerCase().includes(q) || a.role.includes(q))).slice(0, 6);
  }, [agents, query]);

  function track(text: string, caret: number) {
    const before = text.slice(0, caret);
    const m = before.match(/(?:^|\s)@([^\s@]*)$/);
    setQuery(m ? m[1] : null);
    setActive(0);
  }

  function pick(a: Agent) {
    const el = ref.current;
    const caret = el?.selectionStart ?? value.length;
    const before = value.slice(0, caret).replace(/@([^\s@]*)$/, `@${a.name} `);
    const next = before + value.slice(caret);
    setValue(next);
    setQuery(null);
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(before.length, before.length); });
  }

  function send() {
    const body = value.trim();
    if (!body) return;
    onSend(body);
    setValue("");
    setQuery(null);
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (matches.length) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => (i + 1) % matches.length); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => (i - 1 + matches.length) % matches.length); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); pick(matches[active]); return; }
      if (e.key === "Escape") { setQuery(null); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  return (
    <div className="relative">
      {matches.length > 0 && (
        <ul className="absolute bottom-full left-0 mb-2 w-72 overflow-hidden rounded-[12px] border border-rule bg-paper py-1 shadow-[0_8px_24px_rgba(20,19,26,0.10)]" role="listbox">
          {matches.map((a, i) => (
            <li key={a.id}>
              <button
                type="button"
                onMouseDown={(e) => { e.preventDefault(); pick(a); }}
                className={clsx("flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-[13px]", i === active ? "bg-sheet" : "")}
              >
                <AgentGlyph role={a.role} size="sm" />
                <span className="font-semibold text-ink">{a.name}</span>
                <span className="ml-auto text-[11px] text-muted">{a.role}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={ref}
          value={value}
          rows={2}
          disabled={disabled}
          placeholder="Message the room. Type @ to call an agent."
          onChange={(e) => { setValue(e.target.value); track(e.target.value, e.target.selectionStart); }}
          onKeyDown={onKey}
          onClick={(e) => track(value, e.currentTarget.selectionStart)}
          className={clsx(inputClass, "min-h-[52px] resize-none leading-relaxed")}
        />
        <Button onClick={send} disabled={disabled || !value.trim()} aria-label="Send" className="h-[52px] w-[52px] px-0">
          <SendHorizontal className="h-4 w-4" strokeWidth={1.75} />
        </Button>
      </div>
    </div>
  );
}
