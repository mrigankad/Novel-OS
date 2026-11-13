/** Gall mark; a lifted gall variant on dark so it keeps its contrast. */
export function BrandMark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <>
      <img src="/brand/mark.svg" alt="" className={`${className} dark:hidden`} width={24} height={24} draggable={false} />
      <img src="/brand/mark-dark.svg" alt="" className={`${className} hidden dark:block`} width={24} height={24} draggable={false} />
    </>
  );
}

export function BrandLogo() {
  return (
    <span className="inline-flex items-center gap-2.5" role="img" aria-label="Novel OS">
      <BrandMark />
      <span aria-hidden className="font-display text-[19px] font-bold leading-none tracking-[-0.02em] text-ink">
        Novel <span className="text-gall">OS</span>
      </span>
    </span>
  );
}
