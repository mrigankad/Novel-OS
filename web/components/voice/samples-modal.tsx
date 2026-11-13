"use client";

import { useRef, useState } from "react";
import { clsx } from "clsx";
import { FileUp, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { voiceApi, voiceKeys } from "@/lib/api/voice";

type Tab = "paste" | "upload" | "chapter";

export function SamplesModal({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("paste");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [chapter, setChapter] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const toast = useToast();

  const add = useMutation({
    mutationFn: () => {
      if (tab === "upload" && file) return voiceApi.upload(projectId, file, title);
      if (tab === "chapter") return voiceApi.addChapter(projectId, Number(chapter));
      return voiceApi.addText(projectId, text, title);
    },
    onSuccess: (s) => {
      void qc.invalidateQueries({ queryKey: voiceKeys.all(projectId) });
      toast(`Added ${s.word_count.toLocaleString()} words`, "success");
      onClose();
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const ready = tab === "paste" ? text.trim().length > 0 : tab === "upload" ? !!file : Number(chapter) > 0;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(20,19,26,0.32)] p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="samples-title"
        className="w-full max-w-xl rounded-[16px] bg-paper p-6 shadow-[0_24px_64px_rgba(20,19,26,0.2)]"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 id="samples-title" className="font-display text-[22px] font-bold tracking-[-0.02em]">Add writing samples</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-muted hover:text-ink">
            <X size={18} strokeWidth={1.75} />
          </button>
        </div>
        <p className="mt-1 text-[14px] text-body">Your own prose only. A few thousand words is enough to start.</p>

        <div className="mt-5 flex gap-1 border-b border-rule">
          {(["paste", "upload", "chapter"] as Tab[]).map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={clsx("-mb-px border-b-2 px-3 pb-2 text-[13px] font-semibold capitalize",
                tab === t ? "border-ink text-ink" : "border-transparent text-body hover:text-ink")}>
              {t === "chapter" ? "Use a chapter" : t}
            </button>
          ))}
        </div>

        <div className="mt-5 flex flex-col gap-4">
          {tab !== "chapter" && (
            <Field label="Title" hint="optional">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short story, 2023" />
            </Field>
          )}
          {tab === "paste" && (
            <Field label="Text">
              <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-56 font-prose text-[15px]"
                placeholder="Paste a scene or chapter you wrote." />
            </Field>
          )}
          {tab === "upload" && (
            <button type="button" onClick={() => fileRef.current?.click()}
              className="flex flex-col items-center rounded-[16px] border border-dashed border-rule-strong px-6 py-10 text-center hover:border-body">
              <FileUp size={22} strokeWidth={1.75} className="text-body" />
              <span className="mt-2 text-[14px] font-semibold text-ink">{file ? file.name : "Choose a file"}</span>
              <span className="mt-1 text-[12px] text-muted">.txt, .md or .docx</span>
              <input ref={fileRef} type="file" accept=".txt,.md,.docx" className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </button>
          )}
          {tab === "chapter" && (
            <Field label="Chapter number" hint="an approved chapter of this book">
              <Input type="number" min={1} value={chapter} onChange={(e) => setChapter(e.target.value)} />
            </Field>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!ready || add.isPending} onClick={() => add.mutate()}>
            {add.isPending ? "Adding..." : "Add sample"}
          </Button>
        </div>
      </div>
    </div>
  );
}
