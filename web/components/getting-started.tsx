"use client";

import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Check, X } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";
import { BrandIcon } from "@/components/brand-icon";
import type { Project } from "@/lib/api";
import { settingsApi, settingsKeys } from "@/lib/api/settings";

const KEY = "novelos.getting-started.dismissed";
const listeners = new Set<() => void>();

function readDismissed(): boolean {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

/**
 * First-run checklist on the Library. Steps tick themselves off from real data;
 * it hides once everything's done or the writer dismisses it.
 */
export function GettingStarted({ projects }: { projects: Project[] }) {
  // Hidden during SSR (true), real value on the client: no flash, no hydration mismatch.
  const dismissed = useSyncExternalStore(subscribe, readDismissed, () => true);
  const conns = useQuery({ queryKey: settingsKeys.connections, queryFn: settingsApi.connections });

  const connected = (conns.data?.connections.length ?? 0) > 0;
  const def = conns.data?.connections.find((c) => c.is_default);
  const book = projects.find((p) => p.chapter_count > 0) ?? projects[0];
  const wrote = projects.some((p) => p.word_count > 0);

  const steps = [
    {
      done: connected,
      title: "Connect a model",
      body: def ? `Writing with ${def.label}.` : "Ollama Cloud, a local model, your Claude Code login or any API key.",
      href: "/settings/connections",
      cta: "Connect",
      icon: def?.provider ?? "ollama",
    },
    {
      done: projects.length > 0,
      title: "Start a book",
      body: "Give it a working title, or open the sample to see the agents at work.",
      href: book ? `/p/${book.id}` : undefined,
      cta: "Open",
    },
    {
      done: wrote,
      title: "Write or draft a chapter",
      body: "Write it yourself, or ask the Scribe in the Agent room.",
      href: book ? `/p/${book.id}/room` : undefined,
      cta: "Agent room",
    },
    {
      done: false,
      optional: true,
      title: "Teach it your voice",
      body: "Paste a few thousand words of your own writing so every agent writes like you.",
      href: book ? `/p/${book.id}/voice` : undefined,
      cta: "Voice Lab",
    },
    {
      done: false,
      optional: true,
      title: "Connect Claude Code",
      body: "Let Claude Code, Cursor or Codex read your canon and write chapters.",
      href: "/settings/connections",
      cta: "Set up",
      icon: "claude_code",
    },
  ];
  const required = steps.filter((s) => !s.optional);
  const doneCount = required.filter((s) => s.done).length;

  if (dismissed || conns.isLoading || doneCount === required.length) return null;

  const hide = () => {
    try { localStorage.setItem(KEY, "1"); } catch { /* private mode */ }
    listeners.forEach((cb) => cb());
  };

  return (
    <section className="mt-10 rounded-[16px] bg-sheet p-6" aria-label="Getting started">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Getting started · {doneCount} of {required.length}</p>
          <p className="mt-1 font-display text-[24px] font-bold tracking-[-0.02em]">Set up your writers&apos; room</p>
        </div>
        <button type="button" onClick={hide} aria-label="Dismiss getting started"
          className="rounded-[8px] p-1.5 text-muted hover:bg-paper hover:text-ink">
          <X className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>
      <ol className="mt-5 grid gap-px overflow-hidden rounded-[12px] bg-rule sm:grid-cols-5">
        {steps.map((s, i) => (
          <li key={s.title} className="flex flex-col gap-2 bg-paper p-4">
            <div className="flex items-center gap-2">
              <span className={clsx(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold",
                s.done ? "bg-pass text-white" : "bg-sheet text-body ring-1 ring-rule-strong",
              )}>
                {s.done ? <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> : i + 1}
              </span>
              {s.icon && <BrandIcon id={s.icon} size="xs" />}
              {s.optional && <span className="label ml-auto">optional</span>}
            </div>
            <p className={clsx("text-[14px] font-semibold", s.done ? "text-muted line-through decoration-rule-strong" : "text-ink")}>{s.title}</p>
            <p className="text-[12px] leading-relaxed text-body">{s.body}</p>
            {!s.done && s.href && (
              <Link href={s.href} className="mt-auto pt-1 text-[13px] font-semibold text-gall hover:underline">{s.cta} →</Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
