"use client";

import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Check, CircleDashed, X } from "lucide-react";
import { useState } from "react";
import { audioApi, audioKeys } from "@/lib/api/audio";

/** ACX technical checks per file (measured where possible, honest when not) and a launch checklist. */
export function AcxPanel({ projectId }: { projectId: string }) {
  const acx = useQuery({ queryKey: audioKeys.acx(projectId), queryFn: () => audioApi.acx(projectId) });
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const data = acx.data;
  if (acx.isLoading) return <p className="text-[14px] text-muted">Checking files…</p>;
  if (!data) return null;
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <div>
        <h3 className="text-[14px] font-medium text-ink">Technical checks</h3>
        {!data.files.length && <p className="mt-2 text-[14px] text-muted">Render a chapter to check it.</p>}
        {data.files.map((f) => (
          <div key={f.track_id} className="mt-4">
            <p className="text-[13px] text-muted">Chapter {f.chapter}</p>
            <ul className="mt-1 space-y-1">
              {f.checks.map((c) => (
                <li key={c.key} className="flex items-start gap-2 text-[14px]">
                  {c.ok === true ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-pass" strokeWidth={1.75} />
                    : c.ok === false ? <X className="mt-0.5 h-4 w-4 shrink-0 text-fail" strokeWidth={1.75} />
                      : <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-muted" strokeWidth={1.75} />}
                  <span className="text-ink">{c.label}</span>
                  <span className="ml-auto shrink-0 text-right text-[13px] text-muted">{c.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div>
        <h3 className="text-[14px] font-medium text-ink">Before you launch</h3>
        <ul className="mt-3 space-y-2">
          {data.launch_checklist.map((item, i) => (
            <li key={item}>
              <label className="flex cursor-pointer items-start gap-3 text-[14px]">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-[var(--color-gall)]"
                  checked={ticked.has(i)}
                  onChange={() => setTicked((s) => {
                    const n = new Set(s);
                    if (n.has(i)) n.delete(i); else n.add(i);
                    return n;
                  })}
                />
                <span className={clsx(ticked.has(i) ? "text-muted line-through" : "text-body")}>{item}</span>
              </label>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
