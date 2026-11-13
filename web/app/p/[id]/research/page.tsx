import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: research agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Research swarm" description="Browser agents that cite every source." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
