import { AudioLines } from "lucide-react";
import { BrandIcon } from "@/components/brand-icon";

/** OpenAI has a mark in /public/brands; ElevenLabs doesn't, so it gets a neutral glyph, never a fake logo. */
export function AudioProviderIcon({ id }: { id: string }) {
  if (id === "openai") return <BrandIcon id="openai" size="xs" />;
  return <AudioLines className="h-4 w-4 shrink-0 text-body" strokeWidth={1.75} aria-hidden />;
}
