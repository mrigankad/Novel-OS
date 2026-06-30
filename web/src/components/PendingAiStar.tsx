/** Gold star when AI results are ready for user review. */
export default function PendingAiStar({ title = "AI results ready to review" }: { title?: string }) {
  return (
    <span
      className="ml-1 inline-block text-[11px] leading-none text-amber-deep"
      title={title}
      aria-label={title}
    >
      ★
    </span>
  );
}
