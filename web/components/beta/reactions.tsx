import { Coffee, Flame, Heart, HelpCircle, type LucideIcon } from "lucide-react";
import type { Reaction } from "@/lib/api/beta";

export const REACTIONS: { value: Exclude<Reaction, "none">; label: string; icon: LucideIcon }[] = [
  { value: "love", label: "Love this", icon: Heart },
  { value: "confused", label: "Confused", icon: HelpCircle },
  { value: "bored", label: "Bored", icon: Coffee },
  { value: "hooked", label: "Hooked", icon: Flame },
];

export function ReactionIcon({ reaction, className = "h-4 w-4" }: { reaction: Reaction; className?: string }) {
  const r = REACTIONS.find((x) => x.value === reaction);
  if (!r) return null;
  const Icon = r.icon;
  return <Icon className={className} strokeWidth={1.75} aria-label={r.label} role="img" />;
}
