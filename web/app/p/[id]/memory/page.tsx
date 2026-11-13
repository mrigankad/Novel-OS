import MemoryScreen from "@/components/agents/memory-screen";

export default async function MemoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MemoryScreen projectId={id} />;
}
