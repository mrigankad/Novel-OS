"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Select, type SelectOption } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { audioApi, audioKeys, type AudioProvider, type CastRow } from "@/lib/api/audio";
import { AudioProviderIcon } from "./provider-icon";

/** Narrator plus every Codex character: a voice, a style note and a preview each. */
export function CastPanel({ projectId, providers }: { projectId: string; providers: AudioProvider[] }) {
  const cast = useQuery({ queryKey: audioKeys.cast(projectId), queryFn: () => audioApi.cast(projectId) });
  const connected = providers.filter((p) => p.connected);
  const voiceLists = useQueries({
    queries: connected.map((p) => ({
      queryKey: audioKeys.voices(p.id),
      queryFn: () => audioApi.voices(p.id),
      staleTime: 10 * 60_000,
    })),
  });
  const options: SelectOption[] = connected.flatMap((p, i) =>
    (voiceLists[i]?.data ?? []).map((v) => ({
      value: `${p.id}:${v.id}`,
      label: v.name,
      hint: [p.label, v.hint].filter(Boolean).join(" · "),
      icon: <AudioProviderIcon id={p.id} />,
    })),
  );

  if (cast.isLoading) return <p className="text-[14px] text-muted">Loading the cast…</p>;
  const rows = cast.data ?? [];
  return (
    <div className="divide-y divide-rule border-y border-rule">
      {rows.map((row) => (
        <CastRowEditor key={row.codex_entry_id ?? "narrator"} projectId={projectId} row={row} options={options} />
      ))}
      {rows.length === 1 && (
        <p className="py-3 text-[13px] text-muted">
          Add characters in the Codex to give them their own voices. Until then the narrator reads everything.
        </p>
      )}
    </div>
  );
}

function CastRowEditor({ projectId, row, options }: { projectId: string; row: CastRow; options: SelectOption[] }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [style, setStyle] = useState(row.style_instructions);
  const [preview, setPreview] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const value = row.provider && row.voice ? `${row.provider}:${row.voice}` : null;
  const isNarrator = row.codex_entry_id === null;

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const save = useMutation({
    mutationFn: (patch: Partial<CastRow>) => audioApi.saveCast(projectId, {
      codex_entry_id: row.codex_entry_id, provider: row.provider, voice: row.voice,
      style_instructions: style, ...patch,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: audioKeys.cast(projectId) }),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const sample = useMutation({
    mutationFn: () => audioApi.sample(projectId, { provider: row.provider, voice: row.voice, style_instructions: style }),
    onSuccess: (url) => {
      setPreview(url);
      queueMicrotask(() => void audio.current?.play());
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const stop = () => { audio.current?.pause(); setPreview(null); };

  return (
    <div className="grid gap-3 py-4 sm:grid-cols-[minmax(0,160px)_minmax(0,240px)_minmax(0,1fr)_auto] sm:items-center">
      <div className="min-w-0">
        <p className="truncate text-[15px] font-medium text-ink">{row.name}</p>
        <p className="text-[12px] text-muted">{isNarrator ? "Reads everything else" : row.role || "Character"}</p>
      </div>
      <Select
        aria-label={`Voice for ${row.name}`}
        value={value}
        placeholder={isNarrator ? "Choose a narrator…" : "Narrator's voice"}
        options={isNarrator ? options : [{ value: "", label: "Use narrator" }, ...options]}
        onChange={(v) => {
          const [provider, ...rest] = v ? v.split(":") : ["", ""];
          save.mutate({ provider, voice: rest.join(":") });
        }}
      />
      <Input
        aria-label={`Style for ${row.name}`}
        placeholder={isNarrator ? "Warm, unhurried, close third person" : "Dry, clipped, a little amused"}
        value={style}
        onChange={(e) => setStyle(e.target.value)}
        onBlur={() => { if (style !== row.style_instructions) save.mutate({ style_instructions: style }); }}
      />
      <div className="flex items-center gap-2">
        {preview ? (
          <Button variant="secondary" size="sm" onClick={stop} aria-label="Stop preview">
            <Square className="h-3.5 w-3.5" strokeWidth={1.75} /> Stop
          </Button>
        ) : (
          <Button variant="secondary" size="sm" disabled={!value || sample.isPending} onClick={() => sample.mutate()}>
            {sample.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.75} />
              : <Play className="h-3.5 w-3.5" strokeWidth={1.75} />}
            Preview
          </Button>
        )}
        {preview && <audio ref={audio} src={preview} onEnded={() => setPreview(null)} className="hidden" />}
      </div>
    </div>
  );
}
