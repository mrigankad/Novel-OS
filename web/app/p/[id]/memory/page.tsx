import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: agents agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Memory" description="What your agents remember." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
