/** Blue dot — last accessed chapter (binder) or last function on current chapter (buttons). */
export default function ResumeWorkflowDot({ title }: { title: string }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full bg-blue-500 ring-1 ring-blue-500/40"
      title={title}
      aria-label={title}
    />
  );
}
