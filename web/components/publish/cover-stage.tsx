"use client";

import type { CSSProperties } from "react";
import type { CoverDesign, CoverSpec } from "@/lib/api/publish";

const pct = (v: number, of: number) => `${(v / of) * 100}%`;

/**
 * The full wrap at proportional scale, drawn in HTML/CSS. Everything is laid
 * out in percentages of the wrap and type is sized in container units, so the
 * preview stays true to the printed proportions at any width.
 */
export function CoverStage({ spec, cover, title, author, tilt }: {
  spec: CoverSpec; cover: CoverDesign | null; title: string; author: string; tilt?: boolean;
}) {
  const bg = cover?.colors?.background || "#14131a";
  const fg = cover?.colors?.text || "#ffffff";
  const front = cover?.front?.url;
  const W = spec.wrap_w_in;
  const H = spec.wrap_h_in;
  const b = spec.bleed_in;
  const tw = spec.trim_w_in;
  const flat = spec.format === "ebook" || spec.format === "audiobook";
  const frontX = flat ? 0 : b + tw + spec.spine_in;
  const spineText = cover?.spine_text || "";

  const root: CSSProperties = {
    aspectRatio: `${W} / ${H}`, containerType: "inline-size", background: bg, color: fg,
  };

  return (
    <div className={tilt ? "[perspective:1600px]" : undefined}>
      <div
        className="relative w-full overflow-hidden shadow-[0_18px_50px_rgba(20,19,26,0.22)] transition-transform duration-500"
        style={{ ...root, transform: tilt ? "rotateY(-24deg) rotateX(6deg)" : undefined, transformStyle: "preserve-3d" }}
        aria-label="Cover wrap preview"
      >
        {/* Back panel */}
        {!flat && (
          <div className="absolute inset-y-0 left-0 flex flex-col" style={{ width: pct(b + tw, W), padding: `${(b + 0.375) / W * 100}cqw` }}>
            <p className="font-display font-bold leading-tight" style={{ fontSize: `${(0.22 / W) * 100}cqw` }}>{title}</p>
            <p className="mt-[1.2cqw] whitespace-pre-line font-prose leading-snug opacity-90" style={{ fontSize: `${(0.13 / W) * 100}cqw` }}>
              {cover?.back_copy || "Back copy goes here. Write it in the inspector or generate a blurb in Publish."}
            </p>
          </div>
        )}
        {/* Barcode keep-out */}
        {spec.barcode_box && (
          <div
            className="absolute flex items-center justify-center bg-white text-[#14131a]"
            style={{
              left: pct(spec.barcode_box.x_in, W), top: pct(spec.barcode_box.y_in, H),
              width: pct(spec.barcode_box.w_in, W), height: pct(spec.barcode_box.h_in, H),
            }}
          >
            <div className="flex h-[55%] w-[80%] items-end gap-[0.18cqw]">
              {Array.from({ length: 28 }, (_, i) => (
                <span key={i} className="h-full bg-[#14131a]" style={{ width: `${[1, 2, 1, 3][i % 4] * 0.08}cqw` }} />
              ))}
            </div>
            <span className="absolute bottom-[4%] font-sans" style={{ fontSize: `${(0.07 / W) * 100}cqw` }}>ISBN</span>
          </div>
        )}
        {/* Spine */}
        {!flat && spec.spine_in > 0 && (
          <div
            className="absolute inset-y-0 flex items-center justify-center border-x border-white/15"
            style={{ left: pct(b + tw, W), width: pct(spec.spine_in, W) }}
          >
            {spineText && (
              <span
                className="whitespace-nowrap font-display font-bold [writing-mode:vertical-rl]"
                style={{ fontSize: `${Math.min(0.16, spec.spine_in * 0.45) / W * 100}cqw`, opacity: spec.spine_text_allowed ? 1 : 0.35 }}
              >
                {spineText}
              </span>
            )}
          </div>
        )}
        {/* Front */}
        <div className="absolute inset-y-0 right-0 overflow-hidden" style={{ left: pct(frontX, W) }}>
          {front ? (
            <img src={front} alt="Front cover art" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full flex-col items-center justify-between py-[12%] text-center">
              <p className="px-[8%] font-display font-bold leading-[1.02] tracking-[-0.03em]" style={{ fontSize: `${(0.55 / W) * 100}cqw` }}>{title}</p>
              <p className="font-sans font-medium uppercase tracking-[0.14em]" style={{ fontSize: `${(0.17 / W) * 100}cqw` }}>{author}</p>
            </div>
          )}
        </div>
        {/* Bleed (trim line) */}
        {b > 0 && (
          <div className="pointer-events-none absolute border border-dashed border-[#d23f45]"
            style={{ left: pct(b, W), right: pct(b, W), top: pct(b, H), bottom: pct(b, H) }} />
        )}
      </div>
    </div>
  );
}
