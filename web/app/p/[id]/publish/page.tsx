"use client";

import { use } from "react";
import { Launch } from "@/components/publish/launch";

export default function PublishPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <Launch projectId={id} />;
}
