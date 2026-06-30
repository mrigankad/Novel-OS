export default function PanelToggle({ on, onClick, label, border }: {
  on: boolean; onClick: () => void; label: string; border?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      title={`Toggle ${label}`}
      className={`px-2.5 py-1 text-[12px] font-medium transition-colors ${border ? "border-l border-paper-line" : ""} ${
        on ? "bg-ink/[0.06] text-ink-text" : "text-ink-muted hover:bg-ink/5"
      }`}
    >
      {label}
    </button>
  );
}
