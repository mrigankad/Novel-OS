"use client";

// Owner: agents area. Mounted by the chapter writing screen (/p/[id]/write/[n]).
export default function ChapterAgentPanel({ projectId, chapter }: { projectId: string; chapter: number }) {
  void projectId; void chapter;
  return (
    <aside className="w-[340px] shrink-0 border-l border-rule p-5">
      <p className="text-[15px] font-bold">Agents</p>
      <p className="mt-2 text-[13px] text-body">Agent pipeline coming soon.</p>
    </aside>
  );
}
