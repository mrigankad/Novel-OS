import { useState } from "react";
import { api } from "../api/client";
import { useToast } from "./toastContext";

type Msg = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

const SUGGESTIONS = [
  "Raise the stakes in one beat",
  "Shift into dialogue",
  "Add a sensory detail",
  "Plant a quiet hook",
  "Reveal something she notices too late",
];

/** Floating Scribe composer - ChatGPT-style, no full-width bar. */
export default function ContinueChat({
  projectId,
  chapter,
  disabled,
  onAccept,
}: {
  projectId: string;
  chapter: number;
  disabled?: boolean;
  onAccept: (paragraph: string) => void;
}) {
  const toast = useToast();
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [lastProposal, setLastProposal] = useState<string | null>(null);

  async function runInstruction(instruction: string) {
    const text = instruction.trim();
    if (!text || busy || disabled) return;
    setInput("");
    setBusy(true);
    setExpanded(true);
    setLastProposal(null);
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", text }]);
    try {
      const result = await api.continueParagraph(projectId, chapter, text);
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: "assistant", text: result.paragraph },
      ]);
      setLastProposal(result.paragraph);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(msg, "error");
      setMessages((m) => [
        ...m,
        { id: `e-${Date.now()}`, role: "assistant", text: `Couldn't write that: ${msg}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  function send(e?: React.FormEvent) {
    e?.preventDefault();
    void runInstruction(input);
  }

  const showSuggestions = expanded && !busy && !lastProposal && messages.length === 0;

  return (
    <div className="pointer-events-none flex w-full flex-col items-stretch gap-2">
      {expanded && messages.length > 0 && (
        <div className="pointer-events-auto max-h-44 space-y-2 overflow-y-auto rounded-3xl border border-[rgba(74,91,133,0.12)] bg-white/95 px-3.5 py-3 shadow-[0_16px_40px_rgba(40,52,90,0.14)] backdrop-blur-xl">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`rounded-2xl px-3 py-2 text-[13px] leading-relaxed ${
                m.role === "user"
                  ? "ml-6 bg-[rgba(104,103,234,0.1)] text-ink-text"
                  : "mr-4 text-ink-text"
              }`}
            >
              {m.text}
            </div>
          ))}
          {busy && (
            <p className="text-[12.5px] text-ink-muted" aria-live="polite">
              Scribe is writing…
            </p>
          )}
          {lastProposal && (
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  onAccept(lastProposal);
                  toast("Paragraph added to Final", "success");
                  setLastProposal(null);
                  setMessages([]);
                  setExpanded(false);
                }}
              >
                Accept into Final
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setLastProposal(null);
                  setMessages((m) => m.slice(0, -1));
                }}
              >
                Discard
              </button>
            </div>
          )}
        </div>
      )}

      {showSuggestions && (
        <div className="pointer-events-auto rounded-3xl border border-[rgba(74,91,133,0.12)] bg-white/92 px-3 py-2.5 shadow-[0_12px_32px_rgba(40,52,90,0.12)] backdrop-blur-xl">
          <div className="flex flex-wrap justify-center gap-1.5">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                disabled={disabled || busy}
                onClick={() => void runInstruction(s)}
                className="rounded-full border border-[rgba(74,91,133,0.1)] bg-[rgba(104,103,234,0.06)] px-3 py-1.5 text-[12px] font-medium text-ink-muted transition hover:border-[rgba(104,103,234,0.35)] hover:bg-[rgba(104,103,234,0.12)] hover:text-[var(--color-violet)] disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        onSubmit={send}
        className="pointer-events-auto flex items-center gap-2 rounded-full border border-[rgba(74,91,133,0.14)] bg-white/95 py-1.5 pl-4 pr-1.5 shadow-[0_18px_48px_rgba(40,52,90,0.16)] backdrop-blur-xl"
      >
        <input
          className="min-w-0 flex-1 bg-transparent py-2 text-[14px] text-ink-text placeholder:text-paper-muted focus:outline-none"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setExpanded(true)}
          disabled={busy || disabled}
          placeholder="Ask Scribe to write the next paragraph…"
          aria-label="Scribe chat"
          id="scribe-chat-input"
        />
        <button
          type="submit"
          disabled={busy || disabled || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-violet)] text-[15px] font-semibold text-white shadow-[0_8px_18px_rgba(104,103,234,0.35)] transition hover:brightness-105 disabled:opacity-35"
          aria-label="Write"
        >
          →
        </button>
      </form>
    </div>
  );
}
