import type { HTMLAttributes } from "react";
import { ICONS, type IconName } from "../icons/registry";

export type { IconName };
export { FEATURE_ICONS } from "../icons/registry";

type Props = {
  name: IconName;
  className?: string;
  title?: string;
} & Omit<HTMLAttributes<HTMLSpanElement>, "children">;

/** Inline Lucide icon. Color via `currentColor` / parent text color. */
export default function Icon({ name, className = "h-4 w-4", title, ...rest }: Props) {
  const raw = ICONS[name];
  if (!raw) {
    return <span className={className} aria-hidden {...rest} />;
  }
  const html = raw.replace(/<svg([^>]*)>/, (_m, attrs: string) => {
    let a = String(attrs)
      .replace(/\s(width|height)="[^"]*"/g, "")
      .replace(/\sclass="[^"]*"/g, "")
      .replace(/\sstroke="[^"]*"/g, ' stroke="currentColor"');
    if (!/\sstroke=/.test(a)) a += ' stroke="currentColor"';
    const cls = className ? ` class="${className}"` : "";
    const labelled = title
      ? ` role="img" aria-label="${title.replace(/"/g, "&quot;")}"`
      : ' aria-hidden="true"';
    return `<svg${a}${cls}${labelled}>`;
  });

  return <span className="inline-flex shrink-0 [&>svg]:block" dangerouslySetInnerHTML={{ __html: html }} {...rest} />;
}
