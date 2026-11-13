"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function CopyButton({ text, label = "Copy", variant = "secondary" }: {
  text: string; label?: string; variant?: "secondary" | "ghost" | "primary";
}) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      variant={variant}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        } catch { /* clipboard blocked */ }
      }}
    >
      {done ? <Check size={14} strokeWidth={1.75} /> : <Copy size={14} strokeWidth={1.75} />}
      {done ? "Copied" : label}
    </Button>
  );
}
