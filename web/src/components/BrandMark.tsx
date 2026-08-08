import markUrl from "../assets/brand/novel-os-mark.svg";
import logoUrl from "../assets/brand/novel-os-logo.svg";

/** Compact owl mark (favicon art) for small chrome. */
export default function BrandMark({
  className = "h-11 w-11",
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
      width={44}
      height={44}
      draggable={false}
    />
  );
}

/** Full Novel OS wordmark logo for sidebar / hero. */
export function BrandLogo({
  className = "h-24 w-auto",
  title = "Novel OS",
}: {
  className?: string;
  title?: string;
}) {
  return (
    <img
      src={logoUrl}
      alt={title}
      className={className}
      height={96}
      draggable={false}
    />
  );
}
