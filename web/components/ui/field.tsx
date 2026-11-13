import { clsx } from "clsx";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

export const inputClass =
  "w-full rounded-[10px] border border-rule-strong bg-paper px-3 py-2 text-[14px] text-ink " +
  "placeholder:text-muted outline-none transition-colors focus:border-gall";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(inputClass, "h-10", className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={clsx(inputClass, "min-h-24 leading-relaxed", className)} {...rest} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-ink">
        {label}
        {hint && <span className="ml-1 font-normal text-muted">· {hint}</span>}
      </span>
      {children}
    </label>
  );
}
