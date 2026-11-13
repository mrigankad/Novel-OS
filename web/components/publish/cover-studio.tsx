"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Box, Check, Copy, FileDown, ImageDown, Plus, Sparkles, Upload, X } from "lucide-react";
import { GenerateImageSheet } from "@/components/images/generate-image-sheet";
import { useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/page";
import { Select as Dropdown } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { projectsApi, qk } from "@/lib/api";
import {
  coverApi, mediaApi, publishKeys,
  type CoverConcept, type CoverDesign, type CoverFormat, type CoverSpec, type Paper,
} from "@/lib/api/publish";
import { CoverStage } from "./cover-stage";

const S = 1.75;
const FORMATS: { id: CoverFormat; label: string }[] = [
  { id: "ebook", label: "Ebook" },
  { id: "paperback", label: "Paperback wrap" },
  { id: "hardcover", label: "Hardcover" },
  { id: "audiobook", label: "Audiobook 1:1" },
];
const TRIMS = ["5x8", "5.25x8", "5.5x8.5", "6x9", "7x10", "8.5x11"];
const PAPERS: Paper[] = ["cream", "white", "color"];

export function CoverStudio({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [format, setFormat] = useState<CoverFormat>("paperback");
  const [mockup, setMockup] = useState(false);

  const project = useQuery({ queryKey: qk.project(projectId), queryFn: () => projectsApi.get(projectId) });
  const covers = useQuery({ queryKey: publishKeys.covers(projectId), queryFn: () => coverApi.list(projectId) });
  const forFormat = (covers.data ?? []).filter((c) => c.format === format);
  const cover = forFormat.find((c) => c.selected) ?? forFormat[0] ?? null;

  const trim = cover?.trim ?? "5.5x8.5";
  const paper = cover?.paper ?? "cream";
  const spec = useQuery({
    queryKey: publishKeys.spec(projectId, format, trim, paper, cover?.pages),
    queryFn: () => coverApi.spec(projectId, format, trim, paper, cover?.pages),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: publishKeys.all(projectId) });
  const create = useMutation({
    mutationFn: () => coverApi.create(projectId, { format, spine_text: project.data?.title ?? "" }),
    onSuccess: () => void invalidate(),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const title = project.data?.title ?? "";
  const author = project.data?.author ?? "";

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <section className="flex min-w-0 flex-1 flex-col bg-sheet">
        <header className="flex flex-wrap items-center justify-between gap-4 px-4 pt-6 sm:px-8 sm:pt-8">
          <div>
            <p className="eyebrow mb-1">Ship</p>
            <h1 className="font-display text-[32px] font-bold leading-none tracking-[-0.03em] text-ink">Cover studio</h1>
          </div>
          <div role="tablist" aria-label="Cover format" className="flex rounded-[10px] bg-paper p-1 ring-1 ring-rule">
            {FORMATS.map((f) => (
              <button key={f.id} role="tab" type="button" aria-selected={format === f.id} onClick={() => setFormat(f.id)}
                className={clsx("h-8 rounded-[8px] px-3 text-[13px] font-semibold transition-colors",
                  format === f.id ? "bg-inverse text-on-inverse" : "text-body hover:text-ink")}>
                {f.label}
              </button>
            ))}
          </div>
        </header>

        <div className="flex flex-1 items-center justify-center p-4 sm:p-8 lg:p-12">
          {spec.data ? (
            <div className={clsx("w-full", format === "audiobook" ? "max-w-[460px]" : format === "ebook" ? "max-w-[380px]" : "max-w-[980px]")}>
              <CoverStage spec={spec.data} cover={cover} title={title} author={author} />
              <Legend spec={spec.data} />
            </div>
          ) : <Skeleton className="h-[420px] w-full max-w-[900px]" />}
        </div>
      </section>

      <aside className="w-full shrink-0 border-t border-rule bg-paper lg:w-[360px] lg:border-l lg:border-t-0">
        <div className="flex h-full flex-col">
          <div className="flex-1 space-y-8 overflow-y-auto p-6">
            {!covers.isLoading && !cover ? (
              <div className="rounded-[10px] bg-sheet p-5">
                <p className="text-[14px] text-ink">No {FORMATS.find((f) => f.id === format)?.label.toLowerCase()} design yet.</p>
                <Button className="mt-3" size="sm" onClick={() => create.mutate()} disabled={create.isPending}>
                  <Plus size={14} strokeWidth={S} />Start this design
                </Button>
              </div>
            ) : null}
            {spec.data && <PrintSpec spec={spec.data} />}
            {cover && <CoverEditor key={cover.id} projectId={projectId} cover={cover} spec={spec.data} onSaved={invalidate} />}
            <Concepts projectId={projectId} cover={cover} onApplied={invalidate} />
            {cover && <PreflightList projectId={projectId} coverId={cover.id} />}
          </div>
          <div className="flex gap-2 border-t border-rule p-4">
            <Button variant="secondary" className="flex-1" onClick={() => setMockup(true)} disabled={!spec.data}>
              <Box size={16} strokeWidth={S} />3D mockup
            </Button>
            {cover && (format === "paperback" || format === "hardcover") ? (
              <a href={coverApi.exportUrl(projectId, cover.id, "pdf")} className="flex-1">
                <Button className="w-full"><FileDown size={16} strokeWidth={S} />Export print PDF</Button>
              </a>
            ) : cover ? (
              <a href={coverApi.exportUrl(projectId, cover.id, "jpg")} className="flex-1">
                <Button className="w-full"><ImageDown size={16} strokeWidth={S} />Export JPEG</Button>
              </a>
            ) : (
              <Button className="flex-1" disabled><FileDown size={16} strokeWidth={S} />Export print PDF</Button>
            )}
          </div>
        </div>
      </aside>

      {mockup && spec.data && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(20,19,26,0.82)] p-10" role="dialog" aria-modal="true" aria-label="3D mockup" onClick={() => setMockup(false)}>
          <button type="button" aria-label="Close" className="absolute right-6 top-6 text-white" onClick={() => setMockup(false)}><X size={20} strokeWidth={S} /></button>
          <Mockup spec={spec.data} cover={cover} title={title} author={author} />
        </div>
      )}
    </div>
  );
}

function Legend({ spec }: { spec: CoverSpec }) {
  if (spec.format === "ebook" || spec.format === "audiobook") {
    return <p className="mt-4 text-center text-[12px] text-muted">{spec.pixels?.w} × {spec.pixels?.h} px front cover</p>;
  }
  return (
    <div className="mt-4 flex justify-between text-[12px] text-muted">
      <span>Back · {spec.trim_w_in} in</span>
      <span>Spine · {spec.spine_in.toFixed(3)} in</span>
      <span>Front · {spec.trim_w_in} in</span>
      <span className="flex items-center gap-1.5"><span className="inline-block h-0 w-4 border-t border-dashed border-[#d23f45]" />Trim, {spec.bleed_in} in bleed</span>
    </div>
  );
}

function Mockup({ spec, cover, title, author }: { spec: CoverSpec; cover: CoverDesign | null; title: string; author: string }) {
  // Front panel only, tilted, with a spine face for depth.
  const frontSpec: CoverSpec = { ...spec, format: "ebook", wrap_w_in: spec.trim_w_in, wrap_h_in: spec.trim_h_in, bleed_in: 0, spine_in: 0, barcode_box: null };
  const depth = Math.max(12, spec.spine_in * 60);
  return (
    <div className="[perspective:1400px]" onClick={(e) => e.stopPropagation()}>
      <div className="relative w-[min(320px,70vw)] [transform-style:preserve-3d] [transform:rotateY(-28deg)_rotateX(4deg)] transition-transform duration-700 hover:[transform:rotateY(-12deg)_rotateX(2deg)]">
        <CoverStage spec={frontSpec} cover={cover} title={title} author={author} />
        <div className="absolute inset-y-0 left-0 origin-left"
          style={{ width: depth, transform: "rotateY(90deg)", background: cover?.colors?.background || "#14131a", filter: "brightness(0.7)" }} />
      </div>
    </div>
  );
}

function Row({ label, value, accent }: { label: string; value: ReactNode; accent?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-rule py-2 text-[13px] last:border-0">
      <span className="text-body">{label}</span>
      <span className={clsx("text-right font-medium", accent ? "text-gall" : "text-ink")}>{value}</span>
    </div>
  );
}

function PrintSpec({ spec }: { spec: CoverSpec }) {
  const print = spec.format === "paperback" || spec.format === "hardcover";
  return (
    <section>
      <h2 className="label mb-2">Print spec · computed from manuscript</h2>
      {print ? (
        <div>
          <Row label="Trim" value={`${spec.trim.replace("x", " × ")} in`} />
          <Row label="Pages and paper" value={`${spec.pages} pp · ${spec.paper}`} />
          <Row label="Spine width" value={`${spec.spine_in.toFixed(2)} in · ${spec.pages_source}`} accent />
          <Row label="Full wrap" value={`${spec.wrap_w_in.toFixed(3)} × ${spec.wrap_h_in.toFixed(3)} in`} />
          <Row label="Template" value={spec.template ?? "KDP + IngramSpark"} />
        </div>
      ) : (
        <div>
          <Row label="Size" value={`${spec.pixels?.w} × ${spec.pixels?.h} px`} />
          <Row label="Ratio" value={spec.format === "ebook" ? "1 : 1.6" : "1 : 1"} />
          <Row label="Manuscript" value={`${spec.words.toLocaleString()} words`} />
        </div>
      )}
    </section>
  );
}

function CoverEditor({ projectId, cover, spec, onSaved }: { projectId: string; cover: CoverDesign; spec?: CoverSpec; onSaved: () => void }) {
  const toast = useToast();
  const [backCopy, setBackCopy] = useState(cover.back_copy);
  const [spine, setSpine] = useState(cover.spine_text);
  const [pages, setPages] = useState(cover.pages ? String(cover.pages) : "");
  const fileRef = useRef<HTMLInputElement>(null);
  const media = useQuery({ queryKey: publishKeys.media(projectId), queryFn: () => mediaApi.list(projectId) });
  const [generating, setGenerating] = useState(false);

  const save = useMutation({
    mutationFn: (body: Parameters<typeof coverApi.update>[2]) => coverApi.update(projectId, cover.id, body),
    onSuccess: () => onSaved(),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const upload = useMutation({
    mutationFn: (f: File) => mediaApi.upload(projectId, [f], "cover"),
    onSuccess: (rows) => save.mutate({ front_media_id: rows[0].id }),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const print = cover.format === "paperback" || cover.format === "hardcover";
  const budget = spec?.back_copy_budget ?? 0;

  return (
    <section className="space-y-4">
      <h2 className="label">Design</h2>
      {print && (
        <div className="grid grid-cols-3 gap-2">
          <Select label="Trim" value={cover.trim} options={TRIMS} onChange={(v) => save.mutate({ trim: v })} />
          <Select label="Paper" value={cover.paper} options={PAPERS} onChange={(v) => save.mutate({ paper: v as Paper })} />
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-semibold text-ink">Pages</span>
            <Input value={pages} placeholder="auto" inputMode="numeric" onChange={(e) => setPages(e.target.value.replace(/\D/g, ""))}
              onBlur={() => save.mutate(pages ? { pages: Number(pages) } : { clear_pages: true })} />
          </label>
        </div>
      )}

      <div>
        <span className="text-[12px] font-semibold text-ink">Front image</span>
        <GenerateImageSheet projectId={projectId} open={generating} onClose={() => setGenerating(false)} kind="cover"
          initialAspect={cover.format === "audiobook" ? "1:1" : "2:3"}
          onDone={(mediaId) => save.mutate({ front_media_id: mediaId })} />
        <div className="mt-2 grid grid-cols-4 gap-2">
          <button type="button" onClick={() => fileRef.current?.click()}
            className="flex aspect-[2/3] flex-col items-center justify-center gap-1 rounded-[8px] border border-dashed border-rule-strong text-[11px] text-body hover:border-gall hover:text-gall">
            <Upload size={16} strokeWidth={S} />{upload.isPending ? "…" : "Upload"}
          </button>
          <button type="button" onClick={() => setGenerating(true)}
            className="flex aspect-[2/3] flex-col items-center justify-center gap-1 rounded-[8px] bg-wash text-[11px] font-semibold text-gall hover:bg-gall hover:text-on-accent">
            <Sparkles size={16} strokeWidth={S} />Generate
          </button>
          {(media.data ?? []).slice(0, 10).map((m) => (
            <button key={m.id} type="button" onClick={() => save.mutate({ front_media_id: m.id })}
              className={clsx("relative aspect-[2/3] overflow-hidden rounded-[8px] bg-sheet ring-2",
                cover.front_media_id === m.id ? "ring-gall" : "ring-transparent hover:ring-rule-strong")}
              aria-label={`Use ${m.filename}`}>
              {/* Media tiles are user uploads served by the API; next/image is not configured for them. */}
              <img src={m.url} alt="" className="h-full w-full object-cover" />
              {cover.front_media_id === m.id && <Check size={14} strokeWidth={2.5} className="absolute right-1 top-1 rounded-full bg-gall p-0.5 text-on-accent" />}
            </button>
          ))}
        </div>
        <input ref={fileRef} type="file" hidden accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <ColorInput label="Background" value={cover.colors?.background || "#14131a"} onChange={(v) => save.mutate({ colors: { ...cover.colors, background: v } })} />
        <ColorInput label="Type" value={cover.colors?.text || "#ffffff"} onChange={(v) => save.mutate({ colors: { ...cover.colors, text: v } })} />
      </div>

      {print && (
        <>
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] font-semibold text-ink">Back copy
              <span className={clsx("ml-1 font-normal", backCopy.length > budget ? "text-fail" : "text-muted")}>· {backCopy.length} / {budget}</span>
            </span>
            <Textarea value={backCopy} rows={6} onChange={(e) => setBackCopy(e.target.value)} onBlur={() => save.mutate({ back_copy: backCopy })} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] font-semibold text-ink">Spine text
              {spec && !spec.spine_text_allowed && <span className="ml-1 font-normal text-warn">· needs 100+ pages</span>}
            </span>
            <Input value={spine} onChange={(e) => setSpine(e.target.value)} onBlur={() => save.mutate({ spine_text: spine })} />
          </label>
        </>
      )}
      {!cover.selected && (
        <Button size="sm" variant="secondary" onClick={() => save.mutate({ selected: true })}>Use this design for launch</Button>
      )}
    </section>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: readonly string[]; onChange: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[12px] font-semibold text-ink">{label}</span>
      <Dropdown aria-label={label} value={value} onChange={onChange} className="w-full"
        options={options.map((o) => ({ value: o, label: o }))} />
    </div>
  );
}

function ColorInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-[10px] border border-rule-strong px-2 py-1.5">
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)} className="h-6 w-6 cursor-pointer rounded border-0 bg-transparent p-0" />
      <span className="text-[12px] text-body">{label}</span>
    </label>
  );
}

function Concepts({ projectId, cover, onApplied }: { projectId: string; cover: CoverDesign | null; onApplied: () => void }) {
  const toast = useToast();
  const [waiting, setWaiting] = useState(false);
  const concepts = useQuery({
    queryKey: publishKeys.concepts(projectId),
    queryFn: () => coverApi.concepts(projectId),
  });
  const generate = useMutation({
    mutationFn: () => coverApi.generateConcepts(projectId),
    onMutate: () => setWaiting(true),
    onSuccess: () => { toast("The art director is sketching. Concepts appear here when ready."); setTimeout(() => setWaiting(false), 60_000); },
    onError: (e: Error) => { setWaiting(false); toast(e.message, "error"); },
  });
  const setFront = useMutation({
    mutationFn: (mediaId: string) => coverApi.update(projectId, cover!.id, { front_media_id: mediaId }),
    onSuccess: () => onApplied(),
  });
  const apply = useMutation({
    mutationFn: (c: CoverConcept) => coverApi.update(projectId, cover!.id, {
      colors: { ...cover!.colors, background: c.palette[0] ?? "#14131a", text: c.palette[c.palette.length - 1] ?? "#ffffff" },
    }),
    onSuccess: () => onApplied(),
  });

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="label">Concepts · from your Codex</h2>
        <Button size="sm" variant="ai" onClick={() => generate.mutate()} disabled={generate.isPending}>
          <Sparkles size={14} strokeWidth={S} />{(concepts.data?.length ?? 0) > 0 ? "Again" : "Propose 3"}
        </Button>
      </div>
      {waiting && !concepts.data?.length && <Skeleton className="h-28" />}
      <div className="space-y-3">
        {(concepts.data ?? []).map((c, i) => (
          <ConceptCard key={`${c.name}-${i}`} concept={c} projectId={projectId}
            onApply={cover ? () => apply.mutate(c) : undefined}
            onGenerated={cover ? (mediaId) => setFront.mutate(mediaId) : undefined} />
        ))}
      </div>
      {!concepts.data?.length && !waiting && (
        <p className="text-[13px] text-body">Three art-direction briefs with palettes and prompts. Generate one with Google, OpenAI, Runway or Higgsfield, or upload your own art.</p>
      )}
    </section>
  );
}

function ConceptCard({ concept, onApply, projectId, onGenerated }: {
  concept: CoverConcept; onApply?: () => void; projectId: string; onGenerated?: (mediaId: string) => void;
}) {
  const toast = useToast();
  const [generating, setGenerating] = useState(false);
  return (
    <article className="rounded-[10px] bg-sheet p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-display text-[16px] font-bold tracking-[-0.01em] text-ink">{concept.name}</p>
        <div className="flex">
          {concept.palette.map((hex) => (
            <span key={hex} title={hex} className="-ml-1 h-5 w-5 rounded-full ring-2 ring-sheet first:ml-0" style={{ background: hex }} />
          ))}
        </div>
      </div>
      {concept.mood && <p className="mt-1 text-[13px] text-body">{concept.mood}</p>}
      <p className="mt-2 text-[12px] text-body"><span className="font-semibold text-ink">Composition </span>{concept.composition}</p>
      <p className="mt-1 text-[12px] text-body"><span className="font-semibold text-ink">Type </span>{concept.typography}</p>
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="secondary" onClick={() => {
          void navigator.clipboard?.writeText(concept.image_prompt).then(() => toast("Prompt copied", "success"));
        }}><Copy size={14} strokeWidth={S} />Copy prompt</Button>
        <Button size="sm" variant="ai" onClick={() => setGenerating(true)}><Sparkles size={14} strokeWidth={S} />Generate</Button>
        {onApply && concept.palette.length > 0 && <Button size="sm" variant="ghost" onClick={onApply}>Use palette</Button>}
      </div>
      <GenerateImageSheet projectId={projectId} open={generating} onClose={() => setGenerating(false)} kind="cover"
        initialPrompt={concept.image_prompt} initialAspect="2:3" onDone={onGenerated} />
    </article>
  );
}

function PreflightList({ projectId, coverId }: { projectId: string; coverId: string }) {
  const pf = useQuery({ queryKey: publishKeys.preflight(projectId, coverId), queryFn: () => coverApi.preflight(projectId, coverId) });
  return (
    <section>
      <h2 className="label mb-2">Preflight</h2>
      {pf.isLoading ? <Skeleton className="h-24" /> : (
        <ul className="space-y-2">
          {(pf.data?.checks ?? []).map((c) => (
            <li key={c.key} className="flex items-start gap-2.5 text-[13px]">
              <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full",
                c.status === "pass" ? "bg-pass" : c.status === "warn" ? "bg-warn" : "bg-fail")} aria-label={c.status} />
              <span className="min-w-0">
                <span className="text-ink">{c.label}</span>
                <span className="block text-[12px] text-muted">{c.detail}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
