function titleCase(status: string) {
  return status
    .replace(/[_-]+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StatusPill({ status }: { status: string }) {
  return (
    <span className="status-pill" data-status={status.toLowerCase()}>
      {titleCase(status)}
    </span>
  );
}
