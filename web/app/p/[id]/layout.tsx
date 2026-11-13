"use client";

import { use, type ReactNode } from "react";
import { useProjectEvents } from "@/lib/events";

/** Everything under /p/[id] stays live: server events invalidate cached queries. */
export default function ProjectLayout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useProjectEvents(id);
  return children;
}
