import { Link } from "react-router-dom";

export default function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 flex items-center gap-1.5 text-[12.5px] text-ink-muted">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {it.to ? (
            <Link to={it.to} className="transition-colors hover:text-amber-deep">{it.label}</Link>
          ) : (
            <span className="text-ink-text">{it.label}</span>
          )}
          {i < items.length - 1 && <span className="text-paper-muted">/</span>}
        </span>
      ))}
    </nav>
  );
}
