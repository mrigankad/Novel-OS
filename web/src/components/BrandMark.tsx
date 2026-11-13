const markUrl = "/brand/mark.svg";

/** The book-N mark: an open book folded into an N, the gutter drawn as a caret. */
export default function BrandMark({
  className = "h-7 w-7",
  title = "Novel OS",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <img
      src={markUrl}
      alt={title}
      className={className}
      width={28}
      height={28}
      draggable={false}
    />
  );
}

/** Mark + wordmark lockup ("Novel" in ink, "OS" in iron-gall). */
export function BrandLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`} role="img" aria-label="Novel OS">
      <BrandMark className="h-7 w-7 shrink-0" title="" />
      <span
        aria-hidden="true"
        className="font-display text-[20px] font-bold leading-none tracking-[-0.03em] text-ink-text"
      >
        Novel <span className="text-violet">OS</span>
      </span>
    </span>
  );
}
