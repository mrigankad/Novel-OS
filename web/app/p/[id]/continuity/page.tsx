import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: manuscript agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Continuity" description="What the book contradicts." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
