import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { api, type CodexEntry, type RelationshipEdge } from "../api/client";
import Scene from "../components/Scene";
import AddRelationshipModal from "../components/AddRelationshipModal";
import { useToast } from "../components/toastContext";

type Pt = { x: number; y: number };

/** Relationship chart with click/drag-to-link (R3→R4). */
export default function RelationshipChart() {
  const { id = "" } = useParams();
  const toast = useToast();
  const svgRef = useRef<SVGSVGElement>(null);
  const [chars, setChars] = useState<CodexEntry[]>([]);
  const [edges, setEdges] = useState<RelationshipEdge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [prefill, setPrefill] = useState<{ source: string; target: string } | null>(null);
  const [linkFrom, setLinkFrom] = useState<string | null>(null);
  const [rubber, setRubber] = useState<{ from: Pt; to: Pt } | null>(null);

  const load = useCallback(() => {
    api.codex(id, "character").then(setChars).catch((e) => setError(String(e)));
    api.relationships(id).then(setEdges).catch(() => setEdges([]));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!linkFrom) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setLinkFrom(null);
        setRubber(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [linkFrom]);

  const layout = useMemo(() => layoutNodes(chars, edges, 640, 420), [chars, edges]);
  const byId = useMemo(
    () => Object.fromEntries(layout.nodes.map((n) => [n.id, n])),
    [layout.nodes],
  );

  function clientToSvg(clientX: number, clientY: number): Pt {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const local = pt.matrixTransform(ctm.inverse());
    return { x: local.x, y: local.y };
  }

  function hitNode(p: Pt): string | null {
    for (const n of layout.nodes) {
      const dx = n.x - p.x;
      const dy = n.y - p.y;
      if (dx * dx + dy * dy <= 28 * 28) return n.id;
    }
    return null;
  }

  function beginLink(nodeId: string, clientX: number, clientY: number) {
    const n = byId[nodeId];
    if (!n) return;
    setLinkFrom(nodeId);
    const to = clientToSvg(clientX, clientY);
    setRubber({ from: { x: n.x, y: n.y }, to });
  }

  function completeLink(targetId: string | null) {
    const source = linkFrom;
    setLinkFrom(null);
    setRubber(null);
    if (!source || !targetId || source === targetId) return;
    setPrefill({ source, target: targetId });
    setAddOpen(true);
  }

  if (error) {
    return (
      <Scene>
        <div className="px-10 py-12">
          <div className="glass-panel px-4 py-3 text-[13px]">Failed to load: {error}</div>
        </div>
      </Scene>
    );
  }

  return (
    <Scene>
      <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-shell p-3 sm:p-4"
        >
          <div className="glass-panel px-6 py-8 sm:px-10">
            <Link to={`/projects/${id}`} className="mb-6 inline-flex text-[13px] font-medium text-ink-muted hover:text-[var(--color-violet)]">
              ← Dashboard
            </Link>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="eyebrow">Codex</p>
                <h1 className="font-display text-[30px] font-semibold tracking-tight text-ink-text">
                  Relationship chart
                </h1>
                <p className="mt-1.5 text-[13px] text-ink-muted">
                  Drag from one character to another to link them. Continuity watches hostile bonds.
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setPrefill(null); setAddOpen(true); }}
                className="btn-primary"
              >
                + Add link
              </button>
            </div>

            {linkFrom && (
              <p className="mb-3 text-[12.5px] text-[var(--color-violet)]" aria-live="polite">
                Linking from {byId[linkFrom]?.name ?? "…"} - drop on another character (Esc to cancel).
              </p>
            )}

            {chars.length < 2 ? (
              <div className="rounded-[24px] border border-dashed border-[rgba(74,91,133,0.18)] bg-white/45 px-8 py-14 text-center text-[13.5px] text-ink-muted">
                Add at least two characters in the Codex to draw connections.
              </div>
            ) : (
              <div className="overflow-hidden rounded-[24px] border border-[rgba(74,91,133,0.12)] bg-white/50 touch-none">
                <svg
                  ref={svgRef}
                  viewBox="0 0 640 420"
                  className="h-auto w-full select-none"
                  role="img"
                  aria-label="Character relationship chart"
                  onPointerMove={(e) => {
                    if (!linkFrom || !rubber) return;
                    setRubber({ ...rubber, to: clientToSvg(e.clientX, e.clientY) });
                  }}
                  onPointerUp={(e) => {
                    if (!linkFrom) return;
                    const target = hitNode(clientToSvg(e.clientX, e.clientY));
                    completeLink(target);
                  }}
                  onPointerLeave={() => {
                    if (linkFrom) { setLinkFrom(null); setRubber(null); }
                  }}
                >
                  {layout.edges.map((e) => (
                    <g key={e.id}>
                      <line
                        x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
                        stroke="rgba(104,103,234,0.35)"
                        strokeWidth={2}
                      />
                      <text
                        x={(e.x1 + e.x2) / 2}
                        y={(e.y1 + e.y2) / 2 - 6}
                        textAnchor="middle"
                        className="fill-[var(--color-ink-muted)]"
                        style={{ fontSize: 11 }}
                      >
                        {e.label}
                      </text>
                    </g>
                  ))}
                  {rubber && (
                    <line
                      x1={rubber.from.x} y1={rubber.from.y}
                      x2={rubber.to.x} y2={rubber.to.y}
                      stroke="rgba(104,103,234,0.55)"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                    />
                  )}
                  {layout.nodes.map((n) => {
                    const active = linkFrom === n.id;
                    const clipId = `clip-${n.id}`;
                    return (
                      <g
                        key={n.id}
                        transform={`translate(${n.x},${n.y})`}
                        className="cursor-grab active:cursor-grabbing"
                        onPointerDown={(e) => {
                          e.preventDefault();
                          (e.currentTarget as SVGGElement).setPointerCapture?.(e.pointerId);
                          beginLink(n.id, e.clientX, e.clientY);
                        }}
                      >
                        <defs>
                          <clipPath id={clipId}>
                            <circle r={22} />
                          </clipPath>
                        </defs>
                        <circle
                          r={22}
                          fill="url(#nodeGrad)"
                          stroke={active ? "var(--color-violet)" : "rgba(104,103,234,0.35)"}
                          strokeWidth={active ? 2.5 : 1.5}
                        />
                        {n.portraitUrl ? (
                          <image
                            href={n.portraitUrl}
                            x={-22}
                            y={-22}
                            width={44}
                            height={44}
                            clipPath={`url(#${clipId})`}
                            preserveAspectRatio="xMidYMid slice"
                          />
                        ) : (
                          <text textAnchor="middle" dy="0.35em" style={{ fontSize: 13, fontWeight: 600 }} fill="#2a3350">
                            {n.name.charAt(0).toUpperCase()}
                          </text>
                        )}
                        <text textAnchor="middle" y={36} style={{ fontSize: 11 }} fill="#6b7594">
                          {n.name.length > 14 ? `${n.name.slice(0, 12)}…` : n.name}
                        </text>
                      </g>
                    );
                  })}
                  <defs>
                    <linearGradient id="nodeGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor="#eeedff" />
                      <stop offset="100%" stopColor="#e7e7ff" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            )}

            {edges.length > 0 && (
              <ul className="mt-6 space-y-2">
                {edges.map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-3 rounded-2xl border border-[rgba(74,91,133,0.1)] bg-white/60 px-4 py-2.5 text-[13px]">
                    <span className="text-ink-text">
                      <span className="font-medium">{e.source_name}</span>
                      <span className="mx-2 text-ink-muted">· {e.label} ·</span>
                      <span className="font-medium">{e.target_name}</span>
                    </span>
                    <button
                      type="button"
                      className="btn-ghost text-[12px] text-[#c85177]"
                      onClick={async () => {
                        try {
                          await api.deleteRelationship(id, e.id);
                          toast("Link removed", "success");
                          load();
                        } catch (err) {
                          toast(err instanceof Error ? err.message : String(err), "error");
                        }
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </motion.div>
      </div>

      <AddRelationshipModal
        open={addOpen}
        onClose={() => { setAddOpen(false); setPrefill(null); }}
        characters={chars}
        projectId={id}
        onAdded={load}
        prefill={prefill}
      />
    </Scene>
  );
}

function layoutNodes(chars: CodexEntry[], edges: RelationshipEdge[], w: number, h: number) {
  const cx = w / 2;
  const cy = h / 2;
  const r = Math.min(w, h) * 0.32;
  const nodes = chars.map((c, i) => {
    const a = (i / Math.max(chars.length, 1)) * Math.PI * 2 - Math.PI / 2;
    return {
      id: c.id,
      name: c.name,
      portraitUrl: api.assetUrl(c.portrait_url),
      x: cx + Math.cos(a) * r,
      y: cy + Math.sin(a) * r,
    };
  });
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const drawn = edges
    .map((e) => {
      const a = byId[e.source_id];
      const b = byId[e.target_id];
      if (!a || !b) return null;
      return { id: e.id, label: e.label, x1: a.x, y1: a.y, x2: b.x, y2: b.y };
    })
    .filter(Boolean) as { id: string; label: string; x1: number; y1: number; x2: number; y2: number }[];
  return { nodes, edges: drawn };
}
