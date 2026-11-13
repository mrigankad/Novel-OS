"use client";

import { use } from "react";
import { AudioStudio } from "@/components/audio/audio-studio";

export default function AudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AudioStudio projectId={id} />;
}
