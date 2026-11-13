import { Page, PageHeader, EmptyState } from "@/components/ui/page";

// Placeholder. Owner: agents agent.
export default function Placeholder() {
  return (
    <Page>
      <PageHeader eyebrow="Coming together" title="Agent room" description="Assign, chat, and watch agents hand off." />
      <div className="mt-8"><EmptyState title="Being built" body="This screen is under construction." /></div>
    </Page>
  );
}
