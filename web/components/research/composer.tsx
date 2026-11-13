"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { researchApi, researchKeys, type ResearchTaskDetail } from "@/lib/api/research";

export function ResearchComposer({ projectId, onStarted }: { projectId: string; onStarted: (t: ResearchTaskDetail) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [question, setQuestion] = useState("");
  const [chapter, setChapter] = useState("");
  const { data: suggestions } = useQuery({
    queryKey: researchKeys.suggestions(projectId),
    queryFn: () => researchApi.suggestions(projectId),
    staleTime: 5 * 60_000,
  });
  const start = useMutation({
    mutationFn: () => researchApi.create(projectId, {
      question: question.trim(),
      chapter: chapter.trim() ? Number(chapter) : null,
    }),
    onSuccess: (t) => {
      setQuestion("");
      void qc.invalidateQueries({ queryKey: researchKeys.list(projectId) });
      onStarted(t);
    },
    onError: (e) => toast(String(e), "error"),
  });
  const ready = question.trim().length >= 3 && !start.isPending;

  return (
    <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (ready) start.mutate(); }}>
      <Field label="Ask the swarm">
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && ready) start.mutate(); }}
          placeholder="What did a lamplighter carry on his rounds in 1880s London?"
          className="min-h-20"
        />
      </Field>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-36">
          <Field label="Chapter" hint="optional">
            <Input type="number" min={1} value={chapter} onChange={(e) => setChapter(e.target.value)} placeholder="None" />
          </Field>
        </div>
        <div className="flex-1" />
        <Button type="submit" variant="ai" disabled={!ready}>
          <Globe className="h-4 w-4" strokeWidth={1.75} /> {start.isPending ? "Sending browsers" : "Research"}
        </Button>
      </div>
      {suggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuestion(s)}
              className="rounded-full border border-rule px-3 py-1 text-[12px] text-body transition-colors hover:border-gall hover:text-gall"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </form>
  );
}
