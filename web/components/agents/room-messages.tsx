"use client";

import { clsx } from "clsx";
import { ArrowRight, BookmarkPlus, Info, Square } from "lucide-react";
import type { Agent, Message } from "@/lib/api/agents";
import { AgentGlyph } from "./agent-icon";
import { useIsStreaming } from "@/lib/streaming";

export function RoomMessage({
  m, agents, onAction, busy, onStop, runActive,
}: {
  m: Message;
  agents: Map<string, Agent>;
  onAction: (m: Message, action: string) => void;
  busy?: boolean;
  /** Stop the run writing this message (shown while it streams). */
  onStop?: (runId: string) => void;
  /** Whether this message's run is still queued or running. */
  runActive?: boolean;
}) {
  if (m.sender === "author") {
    return (
      <div className="group flex flex-col items-end gap-1">
        <div className="max-w-[78%] whitespace-pre-wrap rounded-[16px] rounded-br-[4px] bg-ink px-4 py-2.5 text-[14px] leading-relaxed text-white">
          {m.body}
        </div>
        <button
          type="button"
          onClick={() => onAction(m, "remember")}
          className="flex items-center gap-1 text-[11px] text-muted opacity-0 transition-opacity hover:text-gall group-hover:opacity-100 focus:opacity-100"
        >
          <BookmarkPlus className="h-3 w-3" strokeWidth={1.75} /> Remember this
        </button>
      </div>
    );
  }
  if (m.sender === "system") {
    return (
      <p className="flex items-center justify-center gap-1.5 text-[12px] text-muted">
        <Info className="h-3 w-3" strokeWidth={1.75} /> {m.body}
      </p>
    );
  }
  const agent = agents.get(m.sender.slice(6));
  const objection = m.intent === "objection";
  const to = m.recipients.map((r) => agents.get(r)?.name).filter(Boolean) as string[];
  return (
    <div className="flex gap-3">
      <AgentGlyph role={agent?.role} size="sm" tone={objection ? "fail" : "soft"} />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-1.5 text-[12px] font-semibold text-ink">
          {agent?.name ?? "Agent"}
          {to.length > 0 && (
            <>
              <ArrowRight className="h-3 w-3 text-muted" strokeWidth={1.75} />
              <span className="text-gall">{to.join(", ")}</span>
            </>
          )}
          {m.intent !== "note" && (
            <span className={clsx("font-normal", objection ? "text-fail" : "text-muted")}>· {m.intent}</span>
          )}
          {onStop && m.run_id && <StopWhileLive id={m.id} runId={m.run_id} active={!!runActive && !m.body} onStop={onStop} />}
        </p>
        <div className={clsx(
          "mt-1 whitespace-pre-wrap text-[14px] leading-relaxed",
          objection ? "rounded-[12px] border border-[color-mix(in_srgb,var(--color-fail)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-fail)_6%,transparent)] px-3 py-2 text-ink" : "text-body",
        )}>
          <StreamingBody id={m.id} body={m.body} />
        </div>
        {m.actions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {m.actions.map((a) => (
              <button
                key={a.action}
                type="button"
                disabled={busy}
                onClick={() => onAction(m, a.action)}
                className={clsx(
                  "h-7 rounded-full border px-3 text-[12px] font-semibold transition-colors disabled:opacity-40",
                  objection ? "border-fail/40 text-fail hover:bg-fail hover:text-white"
                    : "border-rule-strong text-ink hover:border-gall hover:text-gall",
                )}
              >
                {a.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StopWhileLive({ id, runId, active, onStop }: { id: string; runId: string; active: boolean; onStop: (rid: string) => void }) {
  const live = useIsStreaming(id);
  if (!live && !active) return null;
  return (
    <button type="button" onClick={() => onStop(runId)}
      className="ml-1 inline-flex h-6 items-center gap-1 rounded-full border border-rule-strong px-2 text-[11px] font-semibold text-body hover:border-ink hover:text-ink">
      <Square className="h-2.5 w-2.5" strokeWidth={1.75} /> Stop
    </button>
  );
}

/** Agent text that may still be arriving: dots before the first words, a caret while writing. */
function StreamingBody({ id, body }: { id: string; body: string }) {
  const live = useIsStreaming(id);
  if (!body) {
    return (
      <span className="inline-flex items-center gap-1 py-1" aria-label="Writing">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-1.5 w-1.5 animate-pulse rounded-full bg-gall"
            style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </span>
    );
  }
  return (
    <>
      {body}
      {live && <span aria-hidden className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-pulse bg-gall" />}
    </>
  );
}
