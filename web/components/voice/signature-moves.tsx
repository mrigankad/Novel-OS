import { Ban } from "lucide-react";
import type { SignatureMove } from "@/lib/api/voice";

export function SignatureMoves({ moves, never }: { moves: SignatureMove[]; never: string[] }) {
  return (
    <div>
      {moves.length === 0 ? (
        <p className="text-[14px] text-body">Re-learn your voice to extract signature moves.</p>
      ) : (
        <ol className="flex flex-col gap-6">
          {moves.map((m, i) => (
            <li key={i}>
              <blockquote className="border-l-2 border-ink pl-4 font-prose text-[18px] leading-[1.5] text-prose">
                &ldquo;{m.example}&rdquo;
              </blockquote>
              <p className="mt-2 pl-4 text-[13px] leading-relaxed text-body">{m.note}</p>
            </li>
          ))}
        </ol>
      )}
      {never.length > 0 && (
        <div className="mt-8">
          <h3 className="label mb-3">Never</h3>
          <ul className="flex flex-col gap-2">
            {never.map((n) => (
              <li key={n} className="flex items-start gap-2 text-[14px] text-ink">
                <Ban size={15} strokeWidth={1.75} className="mt-0.5 shrink-0 text-fail" />
                {n}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
