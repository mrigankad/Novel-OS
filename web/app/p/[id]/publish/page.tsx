import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: publish agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Publish and distribute" description="Every store, one metadata record." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
