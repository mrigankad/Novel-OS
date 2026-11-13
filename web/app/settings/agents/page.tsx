import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: connections agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Agents and models" description="Pick a model for each agent." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
