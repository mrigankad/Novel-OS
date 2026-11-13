import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: voice agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Voice Lab" description="Your Voice DNA." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
