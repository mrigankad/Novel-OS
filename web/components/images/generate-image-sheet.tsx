"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BrandIcon } from "@/components/brand-icon";
import { Sheet } from "@/components/settings/sheet";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { ASPECTS, imageKeys, imagesApi, type ImageKind } from "@/lib/api/images";

// Google's image service is Nano Banana (the models behind Google Flow).
const ICON: Record<string, string> = { google_flow: "google_flow", gemini: "nanobanana", openai: "openai", runway: "runway", higgsfield: "higgsfield" };

/**
 * Generate an image with a connected service (Google Nano Banana, OpenAI,
 * Runway, Higgsfield). The result lands in Media; onDone receives its id.
 */
export function GenerateImageSheet({
  projectId, open, onClose, kind = "image", codexEntryId, initialPrompt, initialAspect, onDone,
}: {
  projectId: string; open: boolean; onClose: () => void; kind?: ImageKind; codexEntryId?: string | null;
  initialPrompt?: string; initialAspect?: string; onDone?: (mediaId: string) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const providers = useQuery({ queryKey: imageKeys.providers, queryFn: imagesApi.providers, enabled: open });
  const connected = (providers.data ?? []).filter((p) => p.connected);
  const [provider, setProvider] = useState("");
  const [prompt, setPrompt] = useState(initialPrompt ?? "");
  const [aspect, setAspect] = useState(initialAspect ?? (kind === "cover" ? "2:3" : kind === "portrait" ? "3:4" : "3:2"));
  const [runId, setRunId] = useState<string | null>(null);
  const drafted = useRef(false);
  const chosen = provider || connected[0]?.id || "";

  const draft = useMutation({
    mutationFn: () => imagesApi.draftPrompt(projectId, kind, codexEntryId),
    onSuccess: (r) => { setPrompt(r.prompt); setAspect(r.aspect); },
  });
  const draftOnce = draft.mutate;
  // Start from the book: draft a prompt once when the sheet opens with nothing prefilled.
  useEffect(() => {
    if (open && !initialPrompt && !drafted.current) { drafted.current = true; draftOnce(); }
  }, [open, initialPrompt, draftOnce]);

  const run = useQuery({
    queryKey: ["p", projectId, "run", "image", runId],
    queryFn: () => imagesApi.run(projectId, runId!),
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data && ["done", "failed", "cancelled"].includes(q.state.data.status) ? false : 1500),
  });
  useEffect(() => {
    const d = run.data;
    if (!runId || !d) return;
    if (d.status === "done" && d.output.media_id) {
      toast("Image ready", "success");
      void qc.invalidateQueries({ queryKey: ["p", projectId, "publish"] });
      void qc.invalidateQueries({ queryKey: ["p", projectId, "codex"] });
      onDone?.(d.output.media_id);
      onClose();
    } else if (d.status === "failed") {
      toast(d.error.replace(/^ImageGenError: /, ""), "error");
    }
  }, [run.data, runId, toast, qc, projectId, onDone, onClose]);

  const generate = useMutation({
    mutationFn: () => imagesApi.generate(projectId, { prompt, provider: chosen, aspect, kind, codex_entry_id: codexEntryId }),
    onSuccess: (r) => setRunId(r.run_id),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const running = !!runId && !["done", "failed", "cancelled"].includes(run.data?.status ?? "");
  const busy = generate.isPending || running;
  const title = kind === "cover" ? "Cover art" : kind === "portrait" ? "Portrait" : kind === "map" ? "Map" : "Image";

  return (
    <Sheet open={open} onClose={onClose} eyebrow="Generate" title={title}
      footer={
        <div className="flex w-full items-center justify-between gap-3">
          <p className="text-[12px] text-muted">Saved to Media. Usually 10–60 seconds.</p>
          <Button variant="ai" onClick={() => generate.mutate()} disabled={busy || !chosen || prompt.trim().length < 3}>
            <Sparkles size={16} strokeWidth={1.75} /> {busy ? "Generating…" : "Generate"}
          </Button>
        </div>
      }>
      <div className="flex flex-col gap-6">
        <div>
          <p className="label mb-2">Service</p>
          {providers.isLoading ? <p className="text-[13px] text-muted">Checking your connections…</p>
            : connected.length === 0 ? (
              <p className="text-[14px] leading-relaxed text-body">
                No image service connected yet. Add Google Flow (via useapi.net), Google Nano Banana (your Gemini key),
                OpenAI, Runway or Higgsfield in{" "}
                <Link href="/settings/connections" className="font-semibold text-gall hover:underline">Connections</Link>.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Image service">
                {(providers.data ?? []).map((p) => (
                  <button key={p.id} type="button" role="radio" aria-checked={chosen === p.id} disabled={!p.connected}
                    onClick={() => setProvider(p.id)} title={p.connected ? p.notes : `${p.label} isn't connected`}
                    className={clsx("flex items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-left text-[13px] transition-colors",
                      chosen === p.id ? "border-gall bg-wash text-ink" : "border-rule text-body hover:border-rule-strong",
                      !p.connected && "cursor-not-allowed opacity-40")}>
                    <BrandIcon id={ICON[p.id]} size="xs" />
                    <span className="min-w-0 flex-1 truncate font-semibold">{p.label}</span>
                  </button>
                ))}
              </div>
            )}
        </div>

        <div className="flex flex-col gap-2">
          <Field label="Prompt" hint="drafted from your book, edit freely">
            <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={7} className="font-prose text-[15px]" />
          </Field>
          <Button size="sm" variant="ghost" className="self-start" onClick={() => draft.mutate()} disabled={draft.isPending}>
            <Wand2 size={14} strokeWidth={1.75} /> {draft.isPending ? "Drafting…" : "Draft again from the book"}
          </Button>
        </div>

        <div>
          <p className="label mb-2">Shape</p>
          <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Aspect ratio">
            {ASPECTS.map((a) => (
              <button key={a} type="button" role="radio" aria-checked={aspect === a} onClick={() => setAspect(a)}
                className={clsx("h-8 rounded-full px-3 text-[13px] font-medium transition-colors",
                  aspect === a ? "bg-ink text-paper" : "bg-sheet text-body hover:text-ink")}>
                {a}
              </button>
            ))}
          </div>
        </div>

        {busy && (
          <div aria-live="polite">
            <div className="h-1 overflow-hidden rounded-full bg-rule"><div className="h-full w-1/3 animate-pulse rounded-full bg-gall" /></div>
            <p className="mt-2 text-[13px] text-body">Generating with {providers.data?.find((p) => p.id === chosen)?.label}…</p>
          </div>
        )}
      </div>
    </Sheet>
  );
}
