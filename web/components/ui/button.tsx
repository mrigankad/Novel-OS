import { clsx } from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "ai" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-[#2a2933]",
  secondary: "border border-rule-strong bg-paper text-ink hover:border-body",
  ghost: "text-body hover:bg-sheet hover:text-ink",
  ai: "bg-gall text-white hover:bg-gall-hover",
  danger: "border border-rule-strong text-fail hover:border-fail",
};

export function Button({
  variant = "primary", size = "md", className, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-[10px] font-semibold transition-colors",
        "disabled:pointer-events-none disabled:opacity-40",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-[14px]",
        VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  );
}
