import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: connections agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Connections" description="Where the words come from." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
