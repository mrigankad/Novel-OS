import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: publish agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Media and images" description="Import and organise images." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
