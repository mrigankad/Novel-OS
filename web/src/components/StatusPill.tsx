const STATUS_COLOR: Record<string, { fg: string; bg: string }> = {
  planned:   { fg: "#9a6b1e", bg: "rgba(176, 134, 66, 0.14)" },
  drafted:   { fg: "#2f6aa8", bg: "rgba(74, 131, 196, 0.14)" },
  edited:    { fg: "#6f4f96", bg: "rgba(138, 107, 176, 0.14)" },
  validated: { fg: "#3f8b5b", bg: "rgba(79, 157, 107, 0.16)" },
  approved:  { fg: "#3f8b5b", bg: "rgba(79, 157, 107, 0.16)" },
};

const FALLBACK = { fg: "#6b6657", bg: "rgba(107, 102, 87, 0.12)" };

export default function StatusPill({ status }: { status: string }) {
  const c = STATUS_COLOR[status.toLowerCase()] ?? FALLBACK;
  return (
    <span className="status-pill" style={{ color: c.fg, backgroundColor: c.bg }}>
      {status}
    </span>
  );
}
