import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: manuscript agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Chapter" description="Write, with agents beside you." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
