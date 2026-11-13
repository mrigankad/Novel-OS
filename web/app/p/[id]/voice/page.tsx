"use client";

import { use, useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui/page";
import { useToast } from "@/components/ui/toast";
import { SamplesModal } from "@/components/voice/samples-modal";
import { LiftControl, ScoreCard } from "@/components/voice/score-card";
import { SignatureMoves } from "@/components/voice/signature-moves";
import { VoiceRules } from "@/components/voice/voice-rules";
import { TraitBars } from "@/components/voice/trait-bars";
import { voiceApi, voiceKeys, type Lift } from "@/lib/api/voice";
import { useProjectEvents, type ServerEvent } from "@/lib/events";

export default function VoiceLabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [picked, setPicked] = useState<number | null>(null);
  const [learnRun, setLearnRun] = useState<{ run: string; since: string | null } | null>(null);

  const profile = useQuery({ queryKey: voiceKeys.profile(id), queryFn: () => voiceApi.profile(id) });
  const samples = useQuery({ queryKey: voiceKeys.samples(id), queryFn: () => voiceApi.samples(id) });
  const hasSamples = (samples.data?.length ?? 0) > 0;
  const scores = useQuery({
    queryKey: voiceKeys.matchAll(id), queryFn: () => voiceApi.matchAll(id), enabled: hasSamples, retry: false,
  });
  const chapter = picked ?? scores.data?.at(-1)?.chapter ?? null;
  const match = useQuery({
    queryKey: voiceKeys.match(id, chapter ?? 0), queryFn: () => voiceApi.match(id, chapter!),
    enabled: hasSamples && chapter != null, retry: false,
  });

  const learning = learnRun != null && profile.data?.updated_at === learnRun.since;
  const onEvent = useCallback((e: ServerEvent) => {
    if (e.type === "run.updated" && learnRun && e.data.id === learnRun.run && e.data.status === "failed") {
      setLearnRun(null);
      toast(`Re-learn failed: ${String(e.data.error ?? "unknown error")}`, "error");
    }
  }, [learnRun, toast]);
  useProjectEvents(learnRun ? id : undefined, onEvent);

  const learn = useMutation({
    mutationFn: () => voiceApi.learn(id),
    onSuccess: (r) => {
      setLearnRun({ run: r.run_id, since: profile.data?.updated_at ?? null });
      toast("Re-learning your voice. This takes a minute.");
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const setLift = useMutation({
    mutationFn: (lift: Lift) => voiceApi.patchProfile(id, { lift }),
    onSuccess: (p) => qc.setQueryData(voiceKeys.profile(id), p),
    onError: (e: Error) => toast(e.message, "error"),
  });
  const remove = useMutation({
    mutationFn: (sid: string) => voiceApi.removeSample(id, sid),
    onSuccess: () => qc.invalidateQueries({ queryKey: voiceKeys.all(id) }),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const p = profile.data;
  const words = (p?.words_analyzed || p?.sample_words || 0).toLocaleString();
  const n = samples.data?.length ?? 0;
  const rows = match.data?.traits ?? p?.trait_rows ?? [];

  return (
    <Page wide>
      <PageHeader
        eyebrow="VOICE LAB"
        title="Your Voice DNA"
        description={hasSamples
          ? `Learned from ${words} of your words across ${n} sample${n === 1 ? "" : "s"}. Every agent writes against it.`
          : "Give Novel OS some of your own writing. Every agent writes against what it learns."}
        actions={<>
          <Button variant="secondary" onClick={() => setAdding(true)}>
            <FilePlus2 size={16} strokeWidth={1.75} />Add writing samples
          </Button>
          <Button variant="ai" disabled={!hasSamples || learn.isPending || learning} onClick={() => learn.mutate()}>
            <RefreshCw size={16} strokeWidth={1.75} className={learning ? "animate-spin" : undefined} />
            {learning ? "Learning..." : "Re-learn voice"}
          </Button>
        </>}
      />

      {samples.isLoading || profile.isLoading ? (
        <div className="mt-10 grid gap-10 lg:grid-cols-3"><Skeleton className="h-80" /><Skeleton className="h-80" /><Skeleton className="h-80" /></div>
      ) : !hasSamples ? (
        <div className="mt-10">
          <EmptyState title="No writing samples yet"
            body="Paste a scene, upload a .txt, .md or .docx, or use a chapter you've approved. A few thousand words is plenty."
            action={<Button onClick={() => setAdding(true)}><FilePlus2 size={16} strokeWidth={1.75} />Add writing samples</Button>} />
        </div>
      ) : (
        <>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <label htmlFor="voice-chapter" className="text-[13px] font-semibold text-ink">Compare draft</label>
            <Select<number> id="voice-chapter" aria-label="Compare draft" size="sm" value={chapter} disabled={!scores.data?.length}
              onChange={(v) => setPicked(v)} className="min-w-[14rem]"
              placeholder={scores.data?.length ? "Choose a chapter…" : "No drafted chapters yet"}
              options={(scores.data ?? []).map((c) => ({ value: c.chapter, label: `Ch ${c.chapter}${c.title ? `: ${c.title}` : ""} · ${c.score}%` }))} />
            {!p?.exists && <span className="text-[13px] text-body">Traits are measured live. Re-learn to extract signature moves.</span>}
          </div>

          <div className="mt-8 grid gap-12 lg:grid-cols-[1.1fr_1fr_0.9fr]">
            <section>
              <h2 className="label mb-3">Measured traits</h2>
              {rows.length ? <TraitBars rows={rows} chapter={match.data ? chapter : null} />
                : <p className="text-[14px] text-body">Re-learn your voice to measure traits.</p>}
            </section>
            <section>
              <h2 className="label mb-3">Signature moves</h2>
              <SignatureMoves moves={p?.signature_moves ?? []} never={[]} />
              {p && <VoiceRules key={p.updated_at} projectId={id} never={p.never ?? []} styleGuide={p.style_guide ?? ""} />}
            </section>
            <section className="flex flex-col gap-8">
              <ScoreCard projectId={id} match={match.data} loading={match.isLoading && chapter != null} />
              <LiftControl value={p?.lift ?? "me_plus_lift"} disabled={setLift.isPending}
                onChange={(l) => setLift.mutate(l)} />
            </section>
          </div>

          <h2 className="label mt-14 mb-3">Samples</h2>
          <ul className="divide-y divide-rule border-y border-rule">
            {samples.data!.map((s) => (
              <li key={s.id} className="flex items-start gap-4 py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-ink">{s.title || "Untitled"}</p>
                  <p className="mt-0.5 text-[12px] text-muted">
                    {s.word_count.toLocaleString()} words · {s.source.startsWith("chapter:") ? `Chapter ${s.source.slice(8)}` : s.source}
                  </p>
                  <p className="mt-1.5 line-clamp-2 font-prose text-[15px] text-body">{s.excerpt}</p>
                </div>
                <Button variant="ghost" size="sm" aria-label={`Delete ${s.title}`} disabled={remove.isPending}
                  onClick={() => remove.mutate(s.id)}>
                  <Trash2 size={15} strokeWidth={1.75} />
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}

      {adding && <SamplesModal projectId={id} onClose={() => setAdding(false)} />}
    </Page>
  );
}
