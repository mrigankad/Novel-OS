"use client";

import { useMutation } from "@tanstack/react-query";
import { clsx } from "clsx";
import { AlertTriangle, FileText, Upload } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Sheet } from "@/components/settings/sheet";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import type { Project } from "@/lib/api";
import { IMPORT_ACCEPT, MAX_IMPORT_BYTES, transferApi, type ImportReport } from "@/lib/api/transfer";

const DETECTED: Record<string, string> = {
  headings: "Split on headings",
  chapter_lines: "Split on “Chapter” lines",
  separators: "Split on section breaks",
  epub_spine: "Split by the ebook’s chapters",
  single: "One chapter",
};

const fmt = (n: number) => n.toLocaleString("en-US");

/** Drop zone shared by manuscript import and backup restore. */
function DropZone({ accept, label, hint, onFile, busy }: {
  accept: string; label: string; hint: string; onFile: (f: File) => void; busy?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };
  return (
    <button type="button" disabled={busy} onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}
      className={clsx("flex w-full flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed px-6 py-10 text-center transition-colors",
        over ? "border-ink bg-sheet" : "border-rule-strong hover:border-body", busy && "opacity-60")}>
      <Upload className="h-5 w-5 text-body" strokeWidth={1.75} />
      <span className="text-[15px] font-semibold text-ink">{busy ? "Reading…" : label}</span>
      <span className="text-[13px] text-body">{hint}</span>
      <input ref={input} type="file" accept={accept} className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </button>
  );
}

export function ImportSheet({ open, onClose, onDone }: {
  open: boolean; onClose: () => void; onDone: (p: Project) => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [genre, setGenre] = useState("");

  const reset = () => { setFile(null); setReport(null); setTitle(""); setAuthor(""); setGenre(""); };
  const close = () => { reset(); onClose(); };

  const preview = useMutation({
    mutationFn: (f: File) => transferApi.preview(f),
    onSuccess: (r) => { setReport(r); setTitle(r.title); },
    onError: (e) => { setFile(null); toast(String(e.message ?? e), "error"); },
  });
  const commit = useMutation({
    mutationFn: () => transferApi.importBook(file!, { title: title.trim(), author: author.trim(), genre: genre.trim() }),
    onSuccess: (r) => { toast(`Imported ${r.report.chapters.length} chapters`, "success"); reset(); onDone(r.project); },
    onError: (e) => toast(String(e.message ?? e), "error"),
  });
  const restore = useMutation({
    mutationFn: (f: File) => transferApi.restore(f),
    onSuccess: (p) => { toast("Backup restored as a new book", "success"); reset(); onDone(p); },
    onError: (e) => toast(String(e.message ?? e), "error"),
  });

  const choose = (f: File) => {
    if (f.size > MAX_IMPORT_BYTES) { toast("That file is over 25 MB", "error"); return; }
    if (f.name.toLowerCase().endsWith(".zip")) { restore.mutate(f); return; }
    setFile(f);
    setReport(null);
    preview.mutate(f);
  };

  const acts = new Set(report?.chapters.map((c) => c.act)).size > 1;
  const n = report?.chapters.length ?? 0;

  return (
    <Sheet open={open} onClose={close} title={report ? "Check the split" : "Import a manuscript"}
      footer={report ? (
        <>
          <Button variant="ghost" onClick={reset}>Choose another file</Button>
          <Button onClick={() => commit.mutate()} disabled={!n || commit.isPending}>
            {commit.isPending ? "Importing…" : `Import ${n} chapter${n === 1 ? "" : "s"}`}
          </Button>
        </>
      ) : undefined}>
      {!report ? (
        <div className="space-y-8">
          <DropZone accept={IMPORT_ACCEPT} busy={preview.isPending} onFile={choose}
            label={file ? file.name : "Drop your manuscript here"} hint="Word (.docx), Markdown, plain text or EPUB, up to 25 MB" />
          <p className="text-[14px] leading-relaxed text-body">
            We split the file into chapters on its headings or &ldquo;Chapter&rdquo; lines, keep your paragraphs and
            italics, and show you the split before anything is saved.
          </p>
          <div className="border-t border-rule pt-6">
            <p className="text-[14px] font-semibold text-ink">Restore from backup</p>
            <p className="mt-1 text-[13px] text-body">A .novelos.zip from &ldquo;Download backup&rdquo; comes back as a new book, with its Codex, memory and media.</p>
            <RestoreButton busy={restore.isPending} onFile={(f) => restore.mutate(f)} />
          </div>
        </div>
      ) : (
        <div>
          <div className="grid gap-4">
            <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Author"><Input value={author} onChange={(e) => setAuthor(e.target.value)} /></Field>
              <Field label="Genre"><Input value={genre} onChange={(e) => setGenre(e.target.value)} placeholder="Literary" /></Field>
            </div>
          </div>

          <div className="mt-8 flex items-baseline justify-between gap-3 border-b border-rule pb-3">
            <p className="font-display text-[22px] font-bold tracking-[-0.02em] text-ink">{n} chapters</p>
            <p className="text-[13px] text-body">{fmt(report.words)} words · {DETECTED[report.detected_by] ?? report.detected_by}</p>
          </div>

          {report.warnings.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {report.warnings.map((w) => (
                <li key={w} className="flex gap-2 text-[13px] text-body">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" strokeWidth={1.75} />{w}
                </li>
              ))}
            </ul>
          )}

          <ol className="mt-4">
            {report.chapters.map((c, i) => {
              const newAct = acts && (i === 0 || report.chapters[i - 1].act !== c.act);
              return (
                <li key={c.number}>
                  {newAct && <p className="label mb-1 mt-5">Act {c.act}</p>}
                  <div className="flex items-baseline gap-3 border-b border-rule py-2.5">
                    <span className="w-6 shrink-0 text-right text-[12px] tabular-nums text-muted">{c.number}</span>
                    <span className="min-w-0 flex-1 truncate text-[14px] text-ink">{c.title}</span>
                    <span className="shrink-0 text-[12px] tabular-nums text-body">{fmt(c.words)}</span>
                  </div>
                </li>
              );
            })}
          </ol>
          {file && (
            <p className="mt-4 flex items-center gap-2 text-[12px] text-muted">
              <FileText className="h-3.5 w-3.5" strokeWidth={1.75} />{file.name}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
}

function RestoreButton({ busy, onFile }: { busy: boolean; onFile: (f: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button variant="secondary" size="sm" className="mt-3" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? "Restoring…" : "Restore from backup"}
      </Button>
      <input ref={input} type="file" accept=".zip,application/zip" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </>
  );
}
