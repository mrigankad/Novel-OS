import BetaScreen from "@/components/beta/beta-screen";

export default async function BetaPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BetaScreen projectId={id} />;
}
