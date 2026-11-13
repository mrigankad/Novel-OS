"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { audioApi, audioKeys } from "@/lib/api/audio";

/** Respellings applied before text goes to the voice: "Iris Vale" → "EYE-ris VAYL". */
export function Pronunciations({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: audioKeys.pronunciations(projectId), queryFn: () => audioApi.pronunciations(projectId) });
  const [term, setTerm] = useState("");
  const [sayAs, setSayAs] = useState("");
  const [suggested, setSuggested] = useState<string[]>([]);
  const refresh = () => qc.invalidateQueries({ queryKey: audioKeys.pronunciations(projectId) });

  const add = useMutation({
    mutationFn: (p: { term: string; say_as: string }) => audioApi.addPronunciation(projectId, p.term, p.say_as),
    onSuccess: (p) => {
      setTerm(""); setSayAs("");
      setSuggested((s) => s.filter((x) => x.toLowerCase() !== p.term.toLowerCase()));
      void refresh();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });
  const remove = useMutation({
    mutationFn: (rid: string) => audioApi.removePronunciation(projectId, rid),
    onSuccess: () => void refresh(),
  });
  const suggest = useMutation({
    mutationFn: () => audioApi.suggest(projectId),
    onSuccess: (names) => {
      setSuggested(names);
      if (!names.length) toast("Every Codex name already has a pronunciation.", "info");
    },
  });

  const rows = list.data ?? [];
  return (
    <div>
      {rows.length > 0 && (
        <table className="w-full text-left text-[14px]">
          <thead>
            <tr className="text-[12px] text-muted">
              <th className="pb-2 font-medium">Written</th>
              <th className="pb-2 font-medium">Said as</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-rule border-y border-rule">
            {rows.map((p) => (
              <tr key={p.id}>
                <td className="py-2 pr-4 text-ink">{p.term}</td>
                <td className="py-2 pr-4 text-body">{p.say_as}</td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    onClick={() => remove.mutate(p.id)}
                    className="rounded-[6px] p-1 text-muted hover:bg-sheet hover:text-ink"
                    aria-label={`Remove ${p.term}`}
                  >
                    <X className="h-4 w-4" strokeWidth={1.75} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form
        className="mt-3 flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (term.trim() && sayAs.trim()) add.mutate({ term: term.trim(), say_as: sayAs.trim() });
        }}
      >
        <Input className="w-full sm:w-48" placeholder="Iris Vale" value={term} onChange={(e) => setTerm(e.target.value)} aria-label="Written" />
        <Input className="w-full sm:w-48" placeholder="EYE-ris VAYL" value={sayAs} onChange={(e) => setSayAs(e.target.value)} aria-label="Said as" />
        <Button type="submit" variant="secondary" size="sm" disabled={!term.trim() || !sayAs.trim()}>
          <Plus className="h-3.5 w-3.5" strokeWidth={1.75} /> Add
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => suggest.mutate()} disabled={suggest.isPending}>
          <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} /> Suggest from Codex
        </Button>
      </form>
      {suggested.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggested.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => { setTerm(s); setSayAs(""); }}
              className="rounded-full border border-rule-strong px-3 py-1 text-[13px] text-body hover:border-body hover:text-ink"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
