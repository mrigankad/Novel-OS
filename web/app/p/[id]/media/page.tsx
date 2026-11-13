"use client";

import { use } from "react";
import { MediaLibrary } from "@/components/publish/media-library";

export default function MediaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <MediaLibrary projectId={id} />;
}
