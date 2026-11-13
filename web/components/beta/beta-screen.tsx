"use client";

import { clsx } from "clsx";
import { Brain, Check, Copy, Lock, Plus, Sparkles, Trash2, UserPlus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Badge, EmptyState, Page, PageHeader, SectionLabel, Skeleton } from "@/components/ui/page";
import { Select, type SelectOption } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { bookApi, bk as bookKeys } from "@/lib/api/book";
import { betaApi, bk, type BetaComment, type BetaRound, type CommentFilter, type Reaction } from "@/lib/api/beta";
import { Confused, Dropoff, HeatStrip } from "./insights";
import { REACTIONS, ReactionIcon } from "./reactions";

function ago(iso: string | null): string {
  if (!iso) return "Not opened yet";
  const s = (Date.now() - new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`).getTime()) / 1000;
  if (s < 90) return "Just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export default function BetaScreen({ projectId }: { projectId: string }) {
  const { data: rounds, isLoading } = useQuery({ queryKey: bk.rounds(projectId), queryFn: () => betaApi.rounds(projectId) });
  const [picked, setPicked] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const round = rounds?.find((r) => r.id === picked) ?? rounds?.[0] ?? null;

  return (
    <Page wide>
      <PageHeader
        eyebrow="Ship"
        title="Beta readers"
        description="Share chapters by private link, see where readers slow down or light up, and hand the notes to your agents."
        actions={<Button onClick={() => setCreating((v) => !v)}><Plus className="h-4 w-4" strokeWidth={1.75} /> New round</Button>}
      />

      {creating && <NewRound projectId={projectId} onDone={(r) => { setCreating(false); if (r) setPicked(r.id); }} />}

      {isLoading ? <Skeleton className="mt-10 h-40" /> : !rounds?.length ? (
        !creating && (
          <div className="mt-10">
            <EmptyState title="No reading rounds yet" body="Start a round, pick the chapters to share and invite readers. Each reader gets their own private link, no login."
              action={<Button onClick={() => setCreating(true)}>Start a round</Button>} />
          </div>
        )
      ) : round && (
        <>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Select<string> aria-label="Reading round" value={round.id} onChange={setPicked} className="min-w-[240px]"
              options={rounds.map((r): SelectOption<string> => ({
                value: r.id, label: r.name,
                hint: `${r.chapters.length} chapter${r.chapters.length === 1 ? "" : "s"} · ${r.readers.length} reader${r.readers.length === 1 ? "" : "s"}${r.status === "closed" ? " · closed" : ""}`,
              }))} />
            <Badge tone={round.status === "open" ? "pass" : "neutral"} dot>{round.status === "open" ? "Open" : "Closed"}</Badge>
            <span className="text-[13px] text-muted">Chapters {round.chapters.join(", ")}</span>
            <CloseRound projectId={projectId} round={round} />
          </div>
          <Readers projectId={projectId} round={round} />
          <InsightsSection projectId={projectId} roundId={round.id} />
          <Comments projectId={projectId} round={round} />
        </>
      )}
    </Page>
  );
}

function NewRound({ projectId, onDone }: { projectId: string; onDone: (r?: BetaRound) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: chapters } = useQuery({ queryKey: bookKeys.chapters(projectId), queryFn: () => bookApi.chapters(projectId) });
  const [name, setName] = useState("");
  const [sel, setSel] = useState<number[]>([]);
  const create = useMutation({
    mutationFn: () => betaApi.createRound(projectId, { name: name.trim() || "Beta round", chapters: sel }),
    onSuccess: (r) => { void qc.invalidateQueries({ queryKey: bk.rounds(projectId) }); toast("Round started", "success"); onDone(r); },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't start the round", "error"),
  });
  const toggle = (n: number) => setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n].sort((a, b) => a - b)));

  return (
    <section className="mt-8 rounded-[16px] border border-rule p-5 sm:p-6">
      <div className="grid gap-5">
        <Field label="Round name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="First readers, act one" /></Field>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="label">Chapters to share</span>
            {!!chapters?.length && (
              <button type="button" className="text-[13px] text-body hover:text-ink"
                onClick={() => setSel(sel.length === chapters.length ? [] : chapters.map((c) => c.number))}>
                {sel.length === chapters.length ? "Clear" : "Select all"}
              </button>
            )}
          </div>
          {!chapters?.length ? <p className="text-[14px] text-muted">Write a chapter first.</p> : (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Chapters">
              {chapters.map((c) => {
                const on = sel.includes(c.number);
                return (
                  <button key={c.id} type="button" aria-pressed={on} onClick={() => toggle(c.number)}
                    className={clsx("inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] transition-colors",
                      on ? "border-inverse bg-inverse text-on-inverse" : "border-rule-strong text-body hover:border-body hover:text-ink")}>
                    {on && <Check className="h-3.5 w-3.5" strokeWidth={1.75} />}
                    <span className="font-semibold">{c.number}</span>
                    <span className="max-w-[12rem] truncate">{c.title}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onDone()}>Cancel</Button>
          <Button disabled={!sel.length || create.isPending} onClick={() => create.mutate()}>Start round</Button>
        </div>
      </div>
    </section>
  );
}

function CloseRound({ projectId, round }: { projectId: string; round: BetaRound }) {
  const qc = useQueryClient();
  const close = useMutation({
    mutationFn: () => betaApi.closeRound(projectId, round.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: bk.rounds(projectId) }),
  });
  if (round.status !== "open") return null;
  return (
    <Button variant="ghost" size="sm" className="ml-auto" disabled={close.isPending}
      onClick={() => { if (window.confirm("Close this round? Reader links will stop working.")) close.mutate(); }}>
      <Lock className="h-3.5 w-3.5" strokeWidth={1.75} /> Close round
    </Button>
  );
}

function Readers({ projectId, round }: { projectId: string; round: BetaRound }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: bk.rounds(projectId) });
  const add = useMutation({
    mutationFn: () => betaApi.addReader(projectId, round.id, { name: name.trim(), email: email.trim() || undefined }),
    onSuccess: () => { setName(""); setEmail(""); void refresh(); },
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't add the reader", "error"),
  });
  const remove = useMutation({ mutationFn: (rid: string) => betaApi.removeReader(projectId, rid), onSuccess: refresh });
  const copy = async (link: string, id: string) => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${link}`);
      setCopied(id);
      window.setTimeout(() => setCopied((c) => (c === id ? null : c)), 1600);
    } catch { toast("Couldn't copy. Select the link and copy it instead.", "error"); }
  };

  return (
    <section>
      <SectionLabel>Readers</SectionLabel>
      {round.readers.length ? (
        <ul className="divide-y divide-rule border-y border-rule">
          {round.readers.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-[15px] font-semibold text-ink">{r.name}</p>
                <p className="truncate text-[13px] text-muted">
                  {ago(r.last_seen_at)}
                  {r.furthest_chapter > 0 && ` · reached ch ${r.furthest_chapter}`}
                  {r.comments > 0 && ` · ${r.comments} note${r.comments === 1 ? "" : "s"}`}
                </p>
              </div>
              {r.finished && <Badge tone="pass">Finished</Badge>}
              <Button variant="secondary" size="sm" onClick={() => void copy(r.link, r.id)} aria-label={`Copy link for ${r.name}`}>
                {copied === r.id ? <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> : <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />}
                {copied === r.id ? "Copied" : "Copy link"}
              </Button>
              <Button variant="ghost" size="sm" aria-label={`Remove ${r.name}`}
                onClick={() => { if (window.confirm(`Remove ${r.name}? Their link and notes will be deleted.`)) remove.mutate(r.id); }}>
                <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
              </Button>
            </li>
          ))}
        </ul>
      ) : <p className="text-[14px] text-muted">No readers yet. Add one and send them their link.</p>}
      {round.status === "open" && (
        <form className="mt-4 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) add.mutate(); }}>
          <div className="min-w-[10rem] flex-1"><Input aria-label="Reader name" placeholder="Reader name" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className="min-w-[12rem] flex-1"><Input aria-label="Email (optional)" type="email" placeholder="Email (optional)" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <Button type="submit" variant="secondary" disabled={!name.trim() || add.isPending}>
            <UserPlus className="h-4 w-4" strokeWidth={1.75} /> Add reader
          </Button>
        </form>
      )}
    </section>
  );
}

function InsightsSection({ projectId, roundId }: { projectId: string; roundId: string }) {
  const { data } = useQuery({ queryKey: bk.insights(projectId, roundId), queryFn: () => betaApi.insights(projectId, roundId) });
  if (!data) return <Skeleton className="mt-10 h-48" />;
  return (
    <section>
      <SectionLabel>Insights</SectionLabel>
      {!data.readers ? <p className="text-[14px] text-muted">Insights appear once readers start reading.</p> : (
        <div className="grid gap-10 lg:grid-cols-2">
          <Dropoff data={data} />
          <HeatStrip data={data} />
          <div className="lg:col-span-2">
            <h3 className="mb-3 text-[14px] font-semibold text-ink">Where readers got confused</h3>
            <Confused data={data} />
          </div>
        </div>
      )}
    </section>
  );
}

const REACTION_OPTIONS: SelectOption<Reaction | "all">[] = [
  { value: "all", label: "All reactions" },
  ...REACTIONS.map((r) => ({ value: r.value, label: r.label, icon: <r.icon className="h-4 w-4" strokeWidth={1.75} /> })),
];

function Comments({ projectId, round }: { projectId: string; round: BetaRound }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [reaction, setReaction] = useState<Reaction | "all">("all");
  const [reader, setReader] = useState<string>("all");
  const [chapter, setChapter] = useState<number>(0);
  const filter: CommentFilter = {
    round_id: round.id,
    reaction: reaction === "all" ? undefined : reaction,
    reader_id: reader === "all" ? undefined : reader,
    chapter: chapter || undefined,
  };
  const { data: comments } = useQuery({ queryKey: bk.comments(projectId, filter), queryFn: () => betaApi.comments(projectId, filter) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["p", projectId, "beta"] });
  const resolve = useMutation({ mutationFn: (cid: string) => betaApi.resolve(projectId, cid), onSuccess: refresh });
  const teach = useMutation({
    mutationFn: ({ cid, binding }: { cid: string; binding: boolean }) => betaApi.toMemory(projectId, cid, binding),
    onSuccess: (m) => toast(m.kind === "decision" ? "Saved as a binding ruling" : "Saved to shared memory", "success"),
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't save", "error"),
  });
  const summarize = useMutation({
    mutationFn: () => betaApi.summarize(projectId, round.id),
    onSuccess: () => toast("The Editor is reading the notes. Summaries land in each chapter's room.", "success"),
    onError: (e) => toast(e instanceof Error ? e.message : "Couldn't start the summary", "error"),
  });

  const groups = useMemo(() => {
    const m = new Map<number, BetaComment[]>();
    for (const c of comments ?? []) m.set(c.chapter, [...(m.get(c.chapter) ?? []), c]);
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [comments]);

  return (
    <section className="pb-10">
      <div className="mt-10 mb-3 flex flex-wrap items-center gap-2">
        <h2 className="label mr-auto">Notes</h2>
        <Select<number> aria-label="Chapter" size="sm" value={chapter} onChange={setChapter}
          options={[{ value: 0, label: "All chapters" }, ...round.chapters.map((n) => ({ value: n, label: `Chapter ${n}` }))]} />
        <Select<string> aria-label="Reader" size="sm" value={reader} onChange={setReader}
          options={[{ value: "all", label: "All readers" }, ...round.readers.map((r) => ({ value: r.id, label: r.name }))]} />
        <Select<Reaction | "all"> aria-label="Reaction" size="sm" value={reaction} onChange={setReaction} options={REACTION_OPTIONS} />
        <Button variant="ai" size="sm" disabled={summarize.isPending || !comments?.length} onClick={() => summarize.mutate()}>
          <Sparkles className="h-3.5 w-3.5" strokeWidth={1.75} /> Summarize for the Editor
        </Button>
      </div>
      {!groups.length ? <p className="text-[14px] text-muted">No notes match.</p> : groups.map(([n, list]) => (
        <div key={n} className="mt-6">
          <h3 className="mb-2 text-[14px] font-semibold text-ink">Chapter {n}</h3>
          <ul className="divide-y divide-rule border-y border-rule">
            {list.map((c) => (
              <li key={c.id} className={clsx("flex flex-col gap-2 py-4 sm:flex-row sm:items-start sm:gap-4", c.resolved && "opacity-55")}>
                <div className="flex w-6 shrink-0 pt-0.5 text-body">
                  {c.reaction !== "none" ? <ReactionIcon reaction={c.reaction} /> : null}
                </div>
                <div className="min-w-0 flex-1">
                  {c.quote && <p className="font-prose text-[16px] italic leading-[1.5] text-prose">&ldquo;{c.quote}&rdquo;</p>}
                  {c.body && <p className="mt-1 text-[14px] text-ink">{c.body}</p>}
                  <p className="mt-1 text-[12px] text-muted">{c.reader_name} · {ago(c.created_at)}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-1">
                  <Button variant="ghost" size="sm" onClick={() => resolve.mutate(c.id)}>
                    <Check className="h-3.5 w-3.5" strokeWidth={1.75} /> {c.resolved ? "Reopen" : "Resolve"}
                  </Button>
                  <Button variant="ghost" size="sm" title="Save as a non-binding note the agents recall"
                    disabled={teach.isPending} onClick={() => teach.mutate({ cid: c.id, binding: false })}>
                    <Brain className="h-3.5 w-3.5" strokeWidth={1.75} /> Teach the agents
                  </Button>
                  <Button variant="ghost" size="sm" title="Save as a binding author ruling"
                    disabled={teach.isPending} onClick={() => teach.mutate({ cid: c.id, binding: true })}>
                    Make binding
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
