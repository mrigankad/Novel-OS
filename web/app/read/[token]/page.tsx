import type { Metadata } from "next";
import Reader from "@/components/beta/reader";

export const metadata: Metadata = { title: "Reading copy", robots: { index: false, follow: false } };

export default async function ReadPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <Reader token={token} />;
}
