"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Ban, ChevronDown, Plus, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { voiceApi } from "@/lib/api/voice";

/**
 * The author's own rules on top of the learned voice: things the agents must
 * never do, and the style guide every writing agent reads. Both are editable;
 * re-learning the voice proposes new ones but the author has the last word.
 */
export function VoiceRules({ projectId, never, styleGuide }: { projectId: string; never: string[]; styleGuide: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guide, setGuide] = useState(styleGuide);
  const save = useMutation({
    mutationFn: (body: { never?: string[]; style_guide?: string }) => voiceApi.patchProfile(projectId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["p", projectId, "voice"] }),
    onError: (e: Error) => toast(e.message, "error"),
  });

  const add = () => {
    const v = draft.trim();
    if (!v || never.some((n) => n.toLowerCase() === v.toLowerCase())) return;
    save.mutate({ never: [...never, v] });
    setDraft("");
  };

  return (
    <div className="mt-8 flex flex-col gap-6">
      <div>
        <h3 className="label mb-3">Never</h3>
        <ul className="flex flex-col gap-1">
          {never.map((n) => (
            <li key={n} className="group flex items-start gap-2 text-[14px] text-ink">
              <Ban size={15} strokeWidth={1.75} className="mt-0.5 shrink-0 text-fail" />
              <span className="flex-1">{n}</span>
              <button type="button" aria-label={`Remove "${n}"`} onClick={() => save.mutate({ never: never.filter((x) => x !== n) })}
                className="rounded p-0.5 text-muted opacity-0 hover:text-fail focus:opacity-100 group-hover:opacity-100">
                <X size={14} strokeWidth={1.75} />
              </button>
            </li>
          ))}
        </ul>
        <form className="mt-2 flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); add(); }}>
          <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Add a rule, e.g. no dream openings"
            className="h-9 text-[13px]" aria-label="New never rule" />
          <Button type="submit" size="sm" variant="secondary" disabled={!draft.trim() || save.isPending}>
            <Plus size={14} strokeWidth={1.75} /> Add
          </Button>
        </form>
      </div>

      <div>
        <button type="button" onClick={() => { setGuide(styleGuide); setGuideOpen((o) => !o); }} aria-expanded={guideOpen}
          className="flex items-center gap-1.5 text-[13px] font-semibold text-ink hover:text-gall">
          <ChevronDown size={15} strokeWidth={1.75} className={guideOpen ? "rotate-180 transition-transform" : "transition-transform"} />
          Style guide the agents read
        </button>
        {guideOpen && (
          <div className="mt-3 flex flex-col gap-2">
            <Textarea value={guide} onChange={(e) => setGuide(e.target.value)} rows={8} className="font-prose text-[15px]"
              placeholder="Re-learn your voice to draft this, or write your own." />
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setGuideOpen(false)}>Cancel</Button>
              <Button size="sm" disabled={guide === styleGuide || save.isPending}
                onClick={() => save.mutate({ style_guide: guide }, { onSuccess: () => { toast("Style guide saved", "success"); setGuideOpen(false); } })}>
                Save
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
