import type { MouseEvent } from "react";
import { useConfirm } from "./Confirm";

/** Small trash icon — always prompts before running `onConfirm`. */
export default function DeleteButton({
  label,
  message,
  title = "Delete",
  confirmLabel = "Delete",
  onConfirm,
  className = "",
}: {
  label: string;
  message: string;
  title?: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  className?: string;
}) {
  const confirm = useConfirm();

  async function handleClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const ok = await confirm({ title, message, confirmLabel, danger: true });
    if (!ok) return;
    await onConfirm();
  }

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={handleClick}
      className={`rounded-md p-1.5 text-ink-muted transition-colors hover:bg-red-50 hover:text-red-600 ${className}`}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m2 0v12a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V7h12Z"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
