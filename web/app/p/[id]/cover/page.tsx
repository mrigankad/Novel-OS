"use client";

import { use } from "react";
import { CoverStudio } from "@/components/publish/cover-studio";

export default function CoverPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <CoverStudio projectId={id} />;
}
