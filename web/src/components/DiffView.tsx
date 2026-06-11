import { useMemo } from "react";
import { diffWords } from "diff";

export default function DiffView({ oldText, newText }: { oldText: string; newText: string }) {
  const parts = useMemo(() => diffWords(oldText, newText), [oldText, newText]);
  return (
    <div className="prose-manuscript whitespace-pre-wrap text-[14px] leading-relaxed">
      {parts.map((p, i) =>
        p.added ? (
          <ins key={i} className="rounded bg-st-approved/15 text-st-approved no-underline">
            {p.value}
          </ins>
        ) : p.removed ? (
          <del key={i} className="rounded bg-red-500/12 text-red-600">
            {p.value}
          </del>
        ) : (
          <span key={i} className="text-ink-muted">{p.value}</span>
        ),
      )}
    </div>
  );
}
