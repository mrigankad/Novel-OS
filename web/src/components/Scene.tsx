import type { ReactNode } from "react";

/** Atmospheric gradient scene for Library / Dashboard (flagship glass). */
export default function Scene({
  children,
  quiet = false,
  className = "",
}: {
  children: ReactNode;
  quiet?: boolean;
  className?: string;
}) {
  return (
    <div className={`${quiet ? "scene-quiet" : "scene"} min-h-full ${className}`}>
      {!quiet && (
        <>
          <div className="scene-orb scene-orb-a" aria-hidden />
          <div className="scene-orb scene-orb-b" aria-hidden />
          <div className="scene-sweep" aria-hidden />
        </>
      )}
      <div className={`scene-content ${className.includes("h-full") ? "h-full" : ""}`}>{children}</div>
    </div>
  );
}
