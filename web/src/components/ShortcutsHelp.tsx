import { useEffect, useState } from "react";
import Modal from "./Modal";

const SHORTCUTS: [string, string][] = [
  ["⌘K  /  Ctrl-K", "Open the command palette"],
  ["[  /  ]", "Previous / next chapter"],
  ["Ctrl-F", "Find & replace (in the editor)"],
  ["?", "Show this help"],
];

export default function ShortcutsHelp() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const isTyping = () => {
      const el = document.activeElement as HTMLElement | null;
      return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "?" && !isTyping() && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <Modal open={open} onClose={() => setOpen(false)} title="Keyboard shortcuts">
      <dl className="flex flex-col gap-2.5">
        {SHORTCUTS.map(([keys, desc]) => (
          <div key={keys} className="flex items-center justify-between gap-4">
            <dt className="font-mono text-[12.5px] text-ink-muted">{keys}</dt>
            <dd className="text-[13.5px] text-ink-text">{desc}</dd>
          </div>
        ))}
      </dl>
    </Modal>
  );
}
