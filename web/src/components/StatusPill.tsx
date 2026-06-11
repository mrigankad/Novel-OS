export default function StatusPill({ status }: { status: string }) {
  return (
    <span className="status-pill" data-status={status.toLowerCase()}>
      {status}
    </span>
  );
}
