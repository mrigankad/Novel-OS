"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Plug } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState, Page, PageHeader, SectionLabel, Skeleton } from "@/components/ui/page";
import { audioApi, audioKeys } from "@/lib/api/audio";
import { AcxPanel } from "./acx-panel";
import { CastPanel } from "./cast-panel";
import { ChapterList } from "./chapter-list";
import { Pronunciations } from "./pronunciations";

export function AudioStudio({ projectId }: { projectId: string }) {
  const providers = useQuery({ queryKey: audioKeys.providers, queryFn: audioApi.providers });
  const cast = useQuery({ queryKey: audioKeys.cast(projectId), queryFn: () => audioApi.cast(projectId) });
  const chapters = useQuery({ queryKey: audioKeys.chapters(projectId), queryFn: () => audioApi.chapters(projectId) });
  const connected = (providers.data ?? []).some((p) => p.connected);
  const narrator = cast.data?.find((c) => c.codex_entry_id === null);
  const hasNarrator = !!(narrator?.provider && narrator.voice);
  const anyTrack = (chapters.data ?? []).some((c) => c.track);

  return (
    <Page>
      <PageHeader
        eyebrow="Ship"
        title="Audiobook"
        description="Cast voices, teach them your names, and render each chapter to MP3."
        actions={anyTrack ? (
          <a href={audioApi.exportUrl(projectId)} download>
            <Button variant="secondary"><Download className="h-4 w-4" strokeWidth={1.75} /> Download all</Button>
          </a>
        ) : undefined}
      />
      {providers.isLoading ? (
        <Skeleton className="mt-10 h-40" />
      ) : !connected ? (
        <div className="mt-10">
          <EmptyState
            title="Connect a voice service"
            body="Narration uses OpenAI (your existing OpenAI connection works) or ElevenLabs. Keys stay on this machine."
            action={(
              <Link href="/settings/connections">
                <Button><Plug className="h-4 w-4" strokeWidth={1.75} /> Open Connections</Button>
              </Link>
            )}
          />
        </div>
      ) : (
        <>
          <SectionLabel>Cast</SectionLabel>
          <CastPanel projectId={projectId} providers={providers.data ?? []} />
          <SectionLabel>Pronunciations</SectionLabel>
          <Pronunciations projectId={projectId} />
          <SectionLabel>Chapters</SectionLabel>
          {!hasNarrator && <p className="mb-3 text-[14px] text-body">Choose a narrator voice above to start rendering.</p>}
          <ChapterList projectId={projectId} canRender={hasNarrator} />
          <SectionLabel>ACX readiness</SectionLabel>
          <AcxPanel projectId={projectId} />
        </>
      )}
    </Page>
  );
}
