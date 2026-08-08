import { useMemo } from "react";
import { diffWords } from "diff";

export default function DiffView({ oldText, newText }: { oldText: string; newText: string }) {
  const parts = useMemo(() => diffWords(oldText, newText), [oldText, newText]);
  return (
    <div className="prose-manuscript whitespace-pre-wrap text-[13px] leading-relaxed">
      {parts.map((p, i) =>
        p.added ? (
          <ins key={i} className="rounded-[2px] bg-ink text-on-ink no-underline">
            {p.value}
          </ins>
        ) : p.removed ? (
          <del key={i} className="rounded-[2px] bg-paper-card text-ink-muted line-through decoration-ink">
            {p.value}
          </del>
        ) : (
          <span key={i} className="text-ink-muted">{p.value}</span>
        ),
      )}
    </div>
  );
}
