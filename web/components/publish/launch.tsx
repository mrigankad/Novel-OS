"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Check, ChevronDown, ChevronRight, Copy, Download, Sparkles, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Page, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { projectsApi, qk } from "@/lib/api";
import {
  COMPILE_FORMATS, MARKETING_KINDS, publishApi, publishKeys,
  type BookMetadata, type MarketingKind, type Release,
} from "@/lib/api/publish";

const S = 1.75;
const DOT: Record<string, string> = {
  ready: "bg-pass", blocked: "bg-fail", submitted: "bg-gall", live: "bg-ink", todo: "bg-muted",
};

export function Launch({ projectId }: { projectId: string }) {
  const project = useQuery({ queryKey: qk.project(projectId), queryFn: () => projectsApi.get(projectId) });
  const releases = useQuery({ queryKey: publishKeys.releases(projectId), queryFn: () => publishApi.releases(projectId) });
  const done = releases.data?.steps_done ?? 0;
  const total = releases.data?.steps_total ?? 0;

  return (
    <Page wide>
      <header>
        <p className="eyebrow mb-2">Ship</p>
        <h1 className="font-display text-[40px] font-bold leading-[1.05] tracking-[-0.03em] text-ink">
          Launch {project.data?.title ? <span className="font-prose italic font-normal">{project.data.title}</span> : "your book"}
        </h1>
        <div className="mt-5 max-w-xl">
          <div className="h-1.5 overflow-hidden rounded-full bg-sheet">
            <div className="h-full rounded-full bg-ink transition-[width] duration-500" style={{ width: total ? `${(done / total) * 100}%` : "0%" }} />
          </div>
          <p className="mt-2 text-[13px] text-body">{releases.isLoading ? "Checking…" : `${done} of ${total} launch steps done`}</p>
        </div>
      </header>

      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px]">
        <StoreTable projectId={projectId} releases={releases.data?.releases} loading={releases.isLoading} />
        <div className="space-y-8">
          <MetadataVault projectId={projectId} />
          <MarketingKit projectId={projectId} />
          <Downloads projectId={projectId} />
        </div>
      </div>
    </Page>
  );
}

function StoreTable({ projectId, releases, loading }: { projectId: string; releases?: Release[]; loading: boolean }) {
  const [open, setOpen] = useState<string | null>("kdp");
  if (loading) return <Skeleton className="h-80" />;
  return (
    <section>
      <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_120px] border-b border-rule-strong pb-2 text-[12px] font-semibold text-body">
        <span>Store</span><span>Files</span><span>Status</span>
      </div>
      {(releases ?? []).map((r) => (
        <div key={r.store} className="border-b border-rule">
          <button type="button" onClick={() => setOpen(open === r.store ? null : r.store)} aria-expanded={open === r.store}
            className="grid w-full grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_120px] items-center py-4 text-left hover:bg-sheet/60">
            <span className="flex items-center gap-2 text-[15px] font-semibold text-ink">
              {open === r.store ? <ChevronDown size={16} strokeWidth={S} /> : <ChevronRight size={16} strokeWidth={S} />}
              {r.label}
              <span className="text-[12px] font-normal text-muted">{r.done}/{r.total}</span>
            </span>
            <span className="truncate text-[13px] text-body">{r.files.length ? r.files.join(" · ") : "—"}</span>
            <span className="flex items-center gap-2 text-[13px] capitalize text-ink">
              <span className={clsx("h-2 w-2 rounded-full", DOT[r.status] ?? "bg-muted")} />{r.status}
            </span>
          </button>
          {open === r.store && <Checklist projectId={projectId} release={r} />}
        </div>
      ))}
    </section>
  );
}

function Checklist({ projectId, release }: { projectId: string; release: Release }) {
  const qc = useQueryClient();
  const toast = useToast();
  const patch = useMutation({
    mutationFn: (body: Parameters<typeof publishApi.updateRelease>[2]) => publishApi.updateRelease(projectId, release.store, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: publishKeys.releases(projectId) }),
    onError: (e: Error) => toast(e.message, "error"),
  });
  return (
    <div className="pb-5 pl-6">
      <ul className="space-y-2">
        {release.items.map((i) => (
          <li key={i.key} className="flex items-start gap-3 text-[14px]">
            <button type="button" disabled={i.auto}
              onClick={() => patch.mutate({ checklist: { [i.key]: !i.done } })}
              aria-label={i.auto ? `${i.label}: checked automatically` : `Toggle ${i.label}`}
              className={clsx("mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border",
                i.done ? "border-inverse bg-inverse text-on-inverse" : "border-rule-strong bg-paper",
                !i.auto && "cursor-pointer hover:border-ink")}>
              {i.done && <Check size={11} strokeWidth={3} />}
            </button>
            <span className="min-w-0 flex-1">
              <span className={clsx(i.done ? "text-ink" : "text-body")}>{i.label}</span>
              {!i.required && <span className="ml-1 text-[12px] text-muted">optional</span>}
              <span className="block text-[12px] text-muted">{i.auto ? i.detail : "Tick when done"}</span>
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex gap-2">
        {release.status !== "submitted" && release.status !== "live" ? (
          <Button size="sm" variant="secondary" disabled={release.computed_status !== "ready"} onClick={() => patch.mutate({ status: "submitted" })}>Mark submitted</Button>
        ) : (
          <>
            {release.status === "submitted" && <Button size="sm" variant="secondary" onClick={() => patch.mutate({ status: "live" })}>Mark live</Button>}
            <Button size="sm" variant="ghost" onClick={() => patch.mutate({ status: "auto" })}>Reset status</Button>
          </>
        )}
      </div>
    </div>
  );
}

function MetadataVault({ projectId }: { projectId: string }) {
  const meta = useQuery({ queryKey: publishKeys.metadata(projectId), queryFn: () => publishApi.metadata(projectId) });
  return (
    <section className="rounded-[16px] bg-sheet p-6">
      <h2 className="font-display text-[20px] font-bold tracking-[-0.02em] text-ink">Metadata vault</h2>
      <p className="mb-4 text-[13px] text-body">One record, synced to every store.</p>
      {meta.data ? <MetadataForm key={meta.data.updated_at} projectId={projectId} meta={meta.data} /> : <Skeleton className="h-64" />}
    </section>
  );
}

const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

function MetadataForm({ projectId, meta }: { projectId: string; meta: BookMetadata }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState({
    subtitle: meta.subtitle, series: meta.series, series_number: meta.series_number ? String(meta.series_number) : "",
    description: meta.description, keywords: meta.keywords.join(", "), bisac: meta.bisac.join(", "),
    isbn_ebook: meta.isbn_ebook, isbn_print: meta.isbn_print, price: meta.price?.usd ? String(meta.price.usd) : "",
    comps: meta.comps.join("\n"),
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const kw = list(f.keywords);
  const save = useMutation({
    mutationFn: () => publishApi.saveMetadata(projectId, {
      subtitle: f.subtitle, series: f.series, series_number: f.series_number ? Number(f.series_number) : null,
      description: f.description, keywords: kw, bisac: list(f.bisac), isbn_ebook: f.isbn_ebook, isbn_print: f.isbn_print,
      price: f.price ? { ...meta.price, usd: Number(f.price) } : {}, comps: list(f.comps), language: meta.language,
    }),
    onSuccess: () => { toast("Metadata saved", "success"); void qc.invalidateQueries({ queryKey: publishKeys.all(projectId) }); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <Field label="Subtitle"><Input value={f.subtitle} onChange={set("subtitle")} /></Field>
      <div className="grid grid-cols-[1fr_72px] gap-2">
        <Field label="Series"><Input value={f.series} onChange={set("series")} /></Field>
        <Field label="No."><Input value={f.series_number} inputMode="numeric" onChange={set("series_number")} /></Field>
      </div>
      <Field label="Description" hint={`${f.description.length} chars`}><Textarea rows={5} value={f.description} onChange={set("description")} /></Field>
      <Field label="Keywords" hint={`${kw.length} of 7`}>
        <Input value={f.keywords} onChange={set("keywords")} placeholder="comma separated" className={kw.length > 7 ? "border-fail" : undefined} />
      </Field>
      <Field label="BISAC codes" hint="e.g. FIC019000"><Input value={f.bisac} onChange={set("bisac")} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="ISBN ebook"><Input value={f.isbn_ebook} onChange={set("isbn_ebook")} /></Field>
        <Field label="ISBN print"><Input value={f.isbn_print} onChange={set("isbn_print")} /></Field>
      </div>
      <Field label="Price" hint="USD"><Input value={f.price} inputMode="decimal" onChange={set("price")} placeholder="4.99" /></Field>
      <Field label="Comps" hint="one per line"><Textarea rows={3} value={f.comps} onChange={set("comps")} /></Field>
      <Button type="submit" disabled={save.isPending || kw.length > 7}>Save metadata</Button>
    </form>
  );
}

function MarketingKit({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const assets = useQuery({ queryKey: publishKeys.marketing(projectId), queryFn: () => publishApi.marketing(projectId) });
  const gen = useMutation({
    mutationFn: (k: MarketingKind) => publishApi.generateMarketing(projectId, [k]),
    onSuccess: () => toast("Writing. It lands here when the job finishes."),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const del = useMutation({
    mutationFn: (id: string) => publishApi.removeMarketing(projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: publishKeys.marketing(projectId) }),
  });
  const busy: MarketingKind[] = gen.isPending && gen.variables ? [gen.variables] : [];

  return (
    <section>
      <h2 className="font-display text-[20px] font-bold tracking-[-0.02em] text-ink">Marketing kit · from the book</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {MARKETING_KINDS.map(({ kind, label }) => (
          <button key={kind} type="button" onClick={() => gen.mutate(kind)} disabled={busy.includes(kind)}
            className={clsx("inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium transition-colors",
              "bg-wash text-gall hover:bg-gall hover:text-on-accent disabled:opacity-50")}>
            <Sparkles size={13} strokeWidth={S} />{label}
          </button>
        ))}
      </div>
      <div className="mt-4 space-y-4">
        {(assets.data ?? []).map((a) => (
          <article key={a.id} className="border-t border-rule pt-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[12px] font-semibold text-ink">{MARKETING_KINDS.find((k) => k.kind === a.kind)?.label ?? a.kind}
                <span className="ml-1 font-normal text-muted">· {new Date(a.created_at).toLocaleDateString()}</span></span>
              <span className="flex gap-1">
                <IconBtn label="Copy" onClick={() => void navigator.clipboard?.writeText(a.content).then(() => toast("Copied", "success"))}><Copy size={14} strokeWidth={S} /></IconBtn>
                <IconBtn label="Delete" onClick={() => del.mutate(a.id)}><Trash2 size={14} strokeWidth={S} /></IconBtn>
              </span>
            </div>
            <p className="mt-1.5 max-h-48 overflow-y-auto whitespace-pre-line font-prose text-[15px] leading-relaxed text-prose">{a.content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function IconBtn({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return <button type="button" aria-label={label} onClick={onClick} className="rounded-[6px] p-1 text-body hover:bg-sheet hover:text-ink">{children}</button>;
}

function Downloads({ projectId }: { projectId: string }) {
  const caps = useQuery({ queryKey: publishKeys.capabilities(projectId), queryFn: () => publishApi.capabilities(projectId) });
  return (
    <section>
      <h2 className="font-display text-[20px] font-bold tracking-[-0.02em] text-ink">Manuscript files</h2>
      <p className="mb-3 text-[13px] text-body">Built from your chapters, in order{caps.data ? ` · ${caps.data.words.toLocaleString()} words` : ""}.</p>
      <div className="flex flex-wrap gap-2">
        {COMPILE_FORMATS.map(({ format, label }) => {
          const off = format === "pdf" && caps.data && !caps.data.pdf;
          return off ? (
            <Button key={format} size="sm" variant="secondary" disabled title="Install reportlab on the server">{label}</Button>
          ) : (
            <a key={format} href={publishApi.compileUrl(projectId, format)} download>
              <Button size="sm" variant="secondary"><Download size={14} strokeWidth={S} />{label}</Button>
            </a>
          );
        })}
      </div>
    </section>
  );
}
